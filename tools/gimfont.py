"""Font atlases of Initial D Street Stage: GIM, index4, swizzled, 256x256,
16x16 cells (256 glyphs per atlas), palette = white with alpha 0x00..0xff.
Glyph order is given by a *_lst.txt file: "<char>=<index>" per line, cp932.

  python gimfont.py topng <in.gim> <out.png>
"""
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

CELL = 16
DEFAULT_FONT = r'C:\Windows\Fonts\YuGothB.ttc'


class Gim:
    def __init__(self, path):
        self.raw = bytearray(open(path, 'rb').read())
        self._find(0x10, len(self.raw))
        self.w, self.h = 256, 256
        self.stride = self.w // 2
        self.pix = self._unswizzle(bytes(self.raw[self.data_off:self.data_off + self.stride * self.h]))

    def _find(self, off, end):
        while off < end:
            t = struct.unpack_from('<H', self.raw, off)[0]
            size, _, dat = struct.unpack_from('<III', self.raw, off + 4)
            if t in (2, 3):
                self._find(off + dat, off + size)
            if t == 4:
                h = off + 0x10
                _, _, fmt, order, w, hh = struct.unpack_from('<HHHHHH', self.raw, h)
                assert (fmt, order, w, hh) == (4, 1, 256, 256), (fmt, order, w, hh)
                self.data_off = h + struct.unpack_from('<I', self.raw, h + 0x1c)[0]
            off += size

    def _unswizzle(self, px):
        out = bytearray(len(px))
        i = 0
        for by in range(self.h // 8):
            for bx in range(self.stride // 16):
                for r in range(8):
                    dst = (by * 8 + r) * self.stride + bx * 16
                    out[dst:dst + 16] = px[i:i + 16]
                    i += 16
        return out

    def _swizzle(self, px):
        out = bytearray(len(px))
        i = 0
        for by in range(self.h // 8):
            for bx in range(self.stride // 16):
                for r in range(8):
                    src = (by * 8 + r) * self.stride + bx * 16
                    out[i:i + 16] = px[src:src + 16]
                    i += 16
        return out

    def get(self, x, y):
        v = self.pix[y * self.stride + x // 2]
        return (v >> 4) if x & 1 else (v & 15)

    def put(self, x, y, v):
        o = y * self.stride + x // 2
        if x & 1:
            self.pix[o] = (self.pix[o] & 0x0f) | (v << 4)
        else:
            self.pix[o] = (self.pix[o] & 0xf0) | v

    def set_cell(self, slot, alpha16):
        """alpha16: 16x16 list of rows with values 0..15."""
        cx, cy = (slot % 16) * CELL, (slot // 16) * CELL
        for y in range(CELL):
            for x in range(CELL):
                self.put(cx + x, cy + y, alpha16[y][x])

    def save(self, path):
        self.raw[self.data_off:self.data_off + len(self.pix)] = self._swizzle(self.pix)
        open(path, 'wb').write(self.raw)

    def to_png(self, path):
        im = Image.new('L', (self.w, self.h))
        im.putdata([self.get(x, y) * 17 for y in range(self.h) for x in range(self.w)])
        im.save(path)


_font_cache = {}


def render_glyph(ch, font_path=DEFAULT_FONT, size=15, dy=-1):
    key = (font_path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(font_path, size)
    font = _font_cache[key]
    im = Image.new('L', (CELL, CELL), 0)
    dr = ImageDraw.Draw(im)
    l, t, r, b = dr.textbbox((0, 0), ch, font=font)
    x = (CELL - (r - l)) // 2 - l
    y = (CELL - size) // 2 + dy
    dr.text((x, y), ch, fill=255, font=font)
    return [[(im.getpixel((xx, yy)) + 8) // 17 for xx in range(CELL)] for yy in range(CELL)]


def read_lst(path):
    out = []
    for line in open(path, 'rb').read().decode('cp932').splitlines():
        if not line:
            continue
        ch, idx = line.rsplit('=', 1)
        out.append((ch, int(idx)))
    return out


def write_lst(path, items):
    open(path, 'wb').write(''.join(f'{c}={i}\n' for c, i in items).encode('cp932'))


if __name__ == '__main__':
    if sys.argv[1] == 'topng':
        Gim(sys.argv[2]).to_png(sys.argv[3])
