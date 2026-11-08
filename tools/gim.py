"""Generic GIM <-> PNG (PSP texture) for formats RGBA5650/5551/4444/8888, index4, index8.

Also walks @ANA containers ("@ANA", u32 0x10, ..., at 0x20: n * {u32 off, u32 size, char name[8]})
and XBB archives, dumping every GIM it finds.

  python gim.py dump <file (.gim/.ana/xbb[.gz])> <out_dir>
"""
import gzip
import os
import struct
import sys

from PIL import Image

BPP = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8}


def _blocks(d, off, end, out):
    while off + 16 <= end:
        t = struct.unpack_from('<H', d, off)[0]
        size, _, dat = struct.unpack_from('<III', d, off + 4)
        if size == 0:
            break
        out.append((t, off, size))
        if t in (2, 3):
            _blocks(d, off + dat, off + size, out)
        off += size
    return out


def _image_info(d, off, size):
    h = off + 0x10
    _, _, fmt, order, w, hgt = struct.unpack_from('<HHHHHH', d, h)
    doff = struct.unpack_from('<I', d, h + 0x1c)[0]
    return {'fmt': fmt, 'order': order, 'w': w, 'h': hgt, 'data': h + doff,
            'pw': (w * BPP[fmt] + 127) // 128 * 128 // BPP[fmt],  # buffer width (16-byte aligned)
            'ph': (hgt + 7) // 8 * 8 if order == 1 else hgt}


def unswizzle(px, stride, rows):
    out = bytearray(stride * rows)
    i = 0
    for by in range(rows // 8):
        for bx in range(stride // 16):
            for r in range(8):
                dst = (by * 8 + r) * stride + bx * 16
                out[dst:dst + 16] = px[i:i + 16]
                i += 16
    return out


def swizzle(px, stride, rows):
    out = bytearray(stride * rows)
    i = 0
    for by in range(rows // 8):
        for bx in range(stride // 16):
            for r in range(8):
                src = (by * 8 + r) * stride + bx * 16
                out[i:i + 16] = px[src:src + 16]
                i += 16
    return out


def _color(fmt, b, i):
    if fmt == 3:
        return tuple(b[i * 4:i * 4 + 4])
    v = struct.unpack_from('<H', b, i * 2)[0]
    if fmt == 0:
        return ((v & 31) * 255 // 31, (v >> 5 & 63) * 255 // 63, (v >> 11) * 255 // 31, 255)
    if fmt == 1:
        return ((v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31, 255 if v >> 15 else 0)
    return ((v & 15) * 17, (v >> 4 & 15) * 17, (v >> 8 & 15) * 17, (v >> 12) * 17)


def gim_to_image(d):
    bl = _blocks(d, 0x10, len(d), [])
    img = pal = None
    for t, off, size in bl:
        if t == 4 and img is None:
            img = _image_info(d, off, size)
        elif t == 5 and pal is None:
            pal = _image_info(d, off, size)
    bpp = BPP[img['fmt']]
    stride = img['pw'] * bpp // 8
    px = d[img['data']:img['data'] + stride * img['ph']]
    if img['order'] == 1:
        px = unswizzle(px, stride, img['ph'])
    colors = None
    if img['fmt'] in (4, 5):
        pb = d[pal['data']:]
        colors = [_color(pal['fmt'], pb, i) for i in range(pal['w'])]
    im = Image.new('RGBA', (img['w'], img['h']))
    data = []
    for y in range(img['h']):
        row = y * stride
        for x in range(img['w']):
            if bpp == 4:
                v = px[row + x // 2]
                data.append(colors[(v >> 4) if x & 1 else (v & 15)])
            elif bpp == 8:
                data.append(colors[px[row + x]])
            else:
                data.append(_color(img['fmt'], px, row // (bpp // 8) + x))
    im.putdata(data)
    return im, img


def _pack_color(fmt, c):
    r, g, b, a = c
    if fmt == 3:
        return bytes((r, g, b, a))
    if fmt == 0:
        v = (r * 31 // 255) | (g * 63 // 255) << 5 | (b * 31 // 255) << 11
    elif fmt == 1:
        v = (r * 31 // 255) | (g * 31 // 255) << 5 | (b * 31 // 255) << 10 | (a >= 128) << 15
    else:
        v = (r // 17) | (g // 17) << 4 | (b // 17) << 8 | (a // 17) << 12
    return struct.pack('<H', v)


def image_to_gim(orig, im):
    """Return a copy of GIM bytes `orig` with pixels taken from PIL image `im`.
    Size and pixel format stay the same; indexed images get a new palette."""
    d = bytearray(orig)
    bl = _blocks(d, 0x10, len(d), [])
    img = pal = None
    for t, off, size in bl:
        if t == 4 and img is None:
            img = _image_info(d, off, size)
        elif t == 5 and pal is None:
            pal = _image_info(d, off, size)
    if im.size != (img['w'], img['h']):
        raise ValueError(f'size {im.size} != {(img["w"], img["h"])}')
    im = im.convert('RGBA')
    bpp = BPP[img['fmt']]
    stride = img['pw'] * bpp // 8
    px = bytearray(stride * img['ph'])
    if img['fmt'] in (4, 5):
        ncol = 16 if bpp == 4 else 256
        q = im.quantize(colors=min(ncol, pal['w']), method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        pl = q.getpalette(rawmode='RGBA') or []
        cols = [tuple(pl[i:i + 4]) for i in range(0, len(pl), 4)]
        cols += [(0, 0, 0, 0)] * (pal['w'] - len(cols))
        pbytes = b''.join(_pack_color(pal['fmt'], c) for c in cols[:pal['w']])
        d[pal['data']:pal['data'] + len(pbytes)] = pbytes
        idx = q.load()
        for y in range(img['h']):
            for x in range(img['w']):
                v = idx[x, y]
                if bpp == 8:
                    px[y * stride + x] = v
                else:
                    o = y * stride + x // 2
                    px[o] |= (v << 4) if x & 1 else v
    else:
        cb = bpp // 8
        p = im.load()
        for y in range(img['h']):
            for x in range(img['w']):
                o = y * stride + x * cb
                px[o:o + cb] = _pack_color(img['fmt'], p[x, y])
    if img['order'] == 1:
        px = swizzle(px, stride, img['ph'])
    d[img['data']:img['data'] + len(px)] = px
    return bytes(d)


def ana_entries(d):
    """List of (offset, size, name) of the GIMs inside an @ANA blob."""
    n = struct.unpack_from('<I', d, 0x10)[0]
    out = []
    for i in range(n):
        off, size = struct.unpack_from('<II', d, 0x20 + i * 16)
        name = d[0x28 + i * 16:0x30 + i * 16].split(b'\0')[0].decode('ascii', 'replace')
        out.append((off, size, name))
    return out


def find_gims(d, prefix=''):
    """Yield (name, gim_bytes) from GIM / @ANA / XBB data."""
    if d[:4] == b'MIG.':
        yield prefix or 'image', d
    elif d[:4] == b'@ANA':
        n = struct.unpack_from('<I', d, 0x10)[0]
        for i in range(n):
            off, size = struct.unpack_from('<II', d, 0x20 + i * 16)
            name = d[0x28 + i * 16:0x30 + i * 16].split(b'\0')[0].decode('ascii', 'replace')
            yield from find_gims(d[off:off + size], f'{prefix}{i:02d}_{name}')
    elif d[:4] == b'XBB\x01':
        n = struct.unpack_from('<I', d, 4)[0]
        for i in range(n):
            off, size, noff, _ = struct.unpack_from('<IIII', d, 0x20 + i * 16)
            name = d[noff:d.index(b'\0', noff)].decode('cp932')
            yield from find_gims(d[off:off + size], f'{prefix}{name}/')


def _png_name(name):
    return name.strip('/').replace('/', '__') + '.png'


def inject_bytes(d, png_dir, prefix='', done=None):
    """Return d with GIMs replaced by PNGs from png_dir (names as made by dump)."""
    done = [] if done is None else done
    if d[:4] == b'MIG.':
        p = os.path.join(png_dir, _png_name(prefix or 'image'))
        if os.path.exists(p):
            done.append(p)
            return image_to_gim(d, Image.open(p))
        return d
    if d[:4] == b'@ANA':
        out = bytearray(d)
        for i, (off, size, name) in enumerate(ana_entries(d)):
            new = inject_bytes(d[off:off + size], png_dir, f'{prefix}{i:02d}_{name}', done)
            assert len(new) == size
            out[off:off + size] = new
        return bytes(out)
    if d[:4] == b'XBB\x01':
        sys.path.insert(0, os.path.dirname(__file__))
        import xbb
        items = []
        for e in xbb.parse(d):
            data = d[e['off']:e['off'] + e['size']]
            items.append((e['name'], e['hash'], inject_bytes(data, png_dir, f'{prefix}{e["name"]}/', done)))
        return xbb.build(items)
    return d


def inject(src, png_dir, dst):
    raw = open(src, 'rb').read()
    gz = raw[:2] == b'\x1f\x8b'
    d = gzip.decompress(raw) if gz else raw
    done = []
    new = inject_bytes(d, png_dir, '', done)
    if gz:
        with open(dst, 'wb') as f, gzip.GzipFile(filename=os.path.basename(src)[:-3], mode='wb',
                                                 fileobj=f, compresslevel=9, mtime=0) as g:
            g.write(new)
    else:
        open(dst, 'wb').write(new)
    print(f'{src}: replaced {len(done)} images -> {dst}')
    return done


def dump(src, out):
    d = open(src, 'rb').read()
    if d[:2] == b'\x1f\x8b':
        d = gzip.decompress(d)
    os.makedirs(out, exist_ok=True)
    for name, g in find_gims(d):
        try:
            im, info = gim_to_image(g)
        except Exception as e:  # noqa: BLE001
            print('skip', name, e)
            continue
        fn = name.strip('/').replace('/', '__') + '.png'
        im.save(os.path.join(out, fn))
        print(fn, info['w'], info['h'], 'fmt', info['fmt'])


if __name__ == '__main__':
    if sys.argv[1] == 'dump':
        dump(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'inject':
        inject(sys.argv[2], sys.argv[3], sys.argv[4])
