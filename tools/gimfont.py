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
            if t == 5:
                h = off + 0x10
                _, _, pfmt, _, pw, _ = struct.unpack_from('<HHHHHH', self.raw, h)
                assert pfmt == 3, pfmt
                po = h + struct.unpack_from('<I', self.raw, h + 0x1c)[0]
                self.palette = [tuple(self.raw[po + i * 4:po + i * 4 + 4]) for i in range(pw)]
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

    def alpha_index(self, a):
        """Palette index of a white pixel with alpha a (0..255).
        Font palettes are not always a linear ramp (some hold grey shadow colours)."""
        if not hasattr(self, '_amap'):
            cand = [(i, c[3]) for i, c in enumerate(self.palette)
                    if c[3] == 0 or c[:3] == (255, 255, 255)]
            zero = next(i for i, al in cand if al == 0)
            self._amap = [zero if v < 8 else min(cand, key=lambda ia: abs(ia[1] - v))[0] for v in range(256)]
        return self._amap[a]

    def set_cell(self, slot, alpha):
        """alpha: 16x16 list of rows with values 0..255."""
        cx, cy = (slot % 16) * CELL, (slot // 16) * CELL
        for y in range(CELL):
            for x in range(CELL):
                self.put(cx + x, cy + y, self.alpha_index(alpha[y][x]))

    def save(self, path):
        self.raw[self.data_off:self.data_off + len(self.pix)] = self._swizzle(self.pix)
        open(path, 'wb').write(self.raw)

    def to_png(self, path):
        im = Image.new('L', (self.w, self.h))
        im.putdata([self.get(x, y) * 17 for y in range(self.h) for x in range(self.w)])
        im.save(path)


_font_cache = {}


def render_glyph(ch, font_path=DEFAULT_FONT, size=15, dy=-1, stretch=1.25, max_w=15):
    """16x16 glyph, alpha 0..255. Letters are stretched horizontally because the
    game draws every glyph in a fixed 16 px cell."""
    key = (font_path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(font_path, size)
    font = _font_cache[key]
    big = Image.new('L', (CELL * 3, CELL), 0)
    dr = ImageDraw.Draw(big)
    l, t, r, b = dr.textbbox((0, 0), ch, font=font)
    y = (CELL - size) // 2 + dy
    dr.text((CELL - l, y), ch, fill=255, font=font)
    box = big.getbbox()
    im = Image.new('L', (CELL, CELL), 0)
    if box:
        glyph = big.crop((box[0], 0, box[2], CELL))
        w = min(max_w, max(1, round(glyph.width * stretch)))
        glyph = glyph.resize((w, CELL), Image.LANCZOS)
        im.paste(glyph, ((CELL - w) // 2, 0))
    return [[im.getpixel((xx, yy)) for xx in range(CELL)] for yy in range(CELL)]


def render_prop(ch, font_path=DEFAULT_FONT, size=15, dy=-1, gap=1, stretch=1.0):
    """Glyph for the proportional renderer: ink starts at x=1.
    Returns (16x16 alpha rows 0..255, advance width in px)."""
    key = (font_path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(font_path, size)
    font = _font_cache[key]
    big = Image.new('L', (CELL * 3, CELL), 0)
    dr = ImageDraw.Draw(big)
    y = (CELL - size) // 2 + dy
    dr.text((CELL, y), ch, fill=255, font=font)
    box = big.getbbox()
    im = Image.new('L', (CELL, CELL), 0)
    if not box:
        return [[0] * CELL for _ in range(CELL)], max(3, size // 3)
    glyph = big.crop((box[0], 0, box[2], CELL))
    w = min(CELL - 1, max(1, round(glyph.width * stretch)))
    if w != glyph.width:
        glyph = glyph.resize((w, CELL), Image.LANCZOS)
    im.paste(glyph, (1, 0))
    return [[im.getpixel((xx, yy)) for xx in range(CELL)] for yy in range(CELL)], w + 1 + gap


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
