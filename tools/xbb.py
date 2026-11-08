"""Unpack / repack XBB archives (Initial D Street Stage, PSP).

Layout (little endian):
  0x00  "XBB\\x01", u32 count, 0x18 bytes zero
  0x20  count * {u32 offset, u32 size, u32 name_offset, u32 name_hash}
  ....  count * {u32 name_hash, u32 entry_index}   (sorted by hash)
  ....  zero-terminated cp932 names
  ....  file data, each aligned to 0x80; file padded to 0x80

The hash function is unknown, so names and hashes are kept as is.

  python xbb.py unpack <archive[.gz]> <out_dir>
  python xbb.py pack   <in_dir> <archive[.gz]>
"""
import gzip
import json
import os
import struct
import sys

ALIGN = 0x80


def align(x, a=ALIGN):
    return (x + a - 1) // a * a


def load(path):
    raw = open(path, 'rb').read()
    gz = raw[:2] == b'\x1f\x8b'
    return (gzip.decompress(raw) if gz else raw), gz


def parse(d):
    if d[:4] != b'XBB\x01':
        raise ValueError('not an XBB archive')
    n = struct.unpack_from('<I', d, 4)[0]
    entries = []
    for i in range(n):
        off, size, noff, h = struct.unpack_from('<IIII', d, 0x20 + i * 16)
        name = d[noff:d.index(b'\0', noff)].decode('cp932')
        entries.append({'name': name, 'hash': h, 'off': off, 'size': size, 'noff': noff})
    return entries


def unpack(src, out):
    d, gz = load(src)
    entries = parse(d)
    os.makedirs(out, exist_ok=True)
    for e in entries:
        with open(os.path.join(out, e['name']), 'wb') as f:
            f.write(d[e['off']:e['off'] + e['size']])
    manifest = {
        'source': os.path.basename(src),
        'gzip': gz,
        'gzip_name': os.path.basename(src)[:-3] if gz else None,
        'entries': [{'name': e['name'], 'hash': e['hash']} for e in entries],
    }
    with open(os.path.join(out, '_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f'{src}: {len(entries)} files -> {out}')


def build(entries_data):
    """entries_data: list of (name, hash, bytes) in original order."""
    n = len(entries_data)
    names = b''
    noffs = []
    base = 0x20 + n * 16 + n * 8
    for name, _, _ in entries_data:
        noffs.append(base + len(names))
        names += name.encode('cp932') + b'\0'
    pos = align(base + len(names))
    head = bytearray(b'XBB\x01' + struct.pack('<I', n) + b'\0' * 0x18)
    table = bytearray()
    body = bytearray()
    for (name, h, data), noff in zip(entries_data, noffs):
        table += struct.pack('<IIII', pos, len(data), noff, h)
        body += data + b'\0' * (align(len(data)) - len(data))
        pos += align(len(data))
    order = sorted(range(n), key=lambda i: entries_data[i][1])
    htab = b''.join(struct.pack('<II', entries_data[i][1], i) for i in order)
    out = head + table + htab + names
    out += b'\0' * (align(len(out)) - len(out))
    return bytes(out + body)


def save(dst, data, gz, src_name):
    """Write raw archive bytes, gzip-compressed like the original if gz."""
    if gz:
        name = src_name[:-3] if src_name.endswith('.gz') else src_name
        with open(dst, 'wb') as raw:
            with gzip.GzipFile(filename=name, mode='wb', fileobj=raw, compresslevel=9, mtime=0) as g:
                g.write(data)
    else:
        open(dst, 'wb').write(data)


def pack(src, dst):
    m = json.load(open(os.path.join(src, '_manifest.json'), encoding='utf-8'))
    items = []
    for e in m['entries']:
        items.append((e['name'], e['hash'], open(os.path.join(src, e['name']), 'rb').read()))
    d = build(items)
    if m['gzip']:
        # keep the original FNAME field in the gzip header
        with open(dst, 'wb') as raw:
            with gzip.GzipFile(filename=m['gzip_name'], mode='wb', fileobj=raw, compresslevel=9, mtime=0) as g:
                g.write(d)
    else:
        open(dst, 'wb').write(d)
    print(f'{src} -> {dst} ({len(d)} bytes raw)')


if __name__ == '__main__':
    cmd, a, b = sys.argv[1:4]
    {'unpack': unpack, 'pack': pack}[cmd](a, b)
