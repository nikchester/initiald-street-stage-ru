"""Russian glyphs for the text fonts of the game.

A font = <name>_lst.txt (characters in glyph order; the "=N" part is ignored
by the game) + atlases <base>_00.gim, _01 ... Glyph i sits in cell i of the
atlases: per_row = 256 // cell, rows = 256 // cell per atlas.
Every archive holding a copy of a font gets the same new font.

For each font:
  * narrow characters (Cyrillic and the private punctuation/digits/Latin of
    rutext) are drawn left-aligned, matching the width table in BOOT.BIN;
  * characters still missing go into free cells, then into cells of Japanese
    characters no remaining text uses.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import fontset  # noqa: E402
import gim  # noqa: E402
import gimfont  # noqa: E402
import rutext  # noqa: E402

# lst name -> (atlas base name, cell size)
FONTS = {
    'msg_lst.txt': ('msg', 16),
    'lecture_lst.txt': ('font_lecture', 16),
    'charNameTbl_lst.txt': ('charName', 16),
    'lobbymes_lst.txt': ('lobbymes', 16),
    'garage_msg_lst.txt': ('garage_msg', 16),
    'cardtext_lst.txt': ('cardtext', 16),
    'hp_lst.txt': ('hp', 16),
    'ms_error_lst.txt': ('ms_error', 16),
    'message_lst.txt': ('mess', 16),
    'replay_lst.txt': ('replay', 16),
    'driverfile_lst.txt': ('driverfile', 16),
    'rivaltalkfont_lst.txt': ('rivaltalkfont', 16),
    'PSP_option_player_18font_lst.txt': ('PSP_option_player_18font', 22),
}


class Atlas:
    """Indexed (4 or 8 bit) 256x256 GIM with an RGBA8888 palette."""

    def __init__(self, data):
        self.raw = bytearray(data)
        img = pal = None
        for t, off, size in gim._blocks(self.raw, 0x10, len(self.raw), []):
            if t == 4 and img is None:
                img = gim._image_info(self.raw, off, size)
            elif t == 5 and pal is None:
                pal = gim._image_info(self.raw, off, size)
        assert img['fmt'] in (4, 5) and pal['fmt'] == 3, (img['fmt'], pal['fmt'])
        self.img = img
        self.bpp = gim.BPP[img['fmt']]
        self.w, self.h = img['w'], img['h']
        self.stride = img['pw'] * self.bpp // 8
        px = bytes(self.raw[img['data']:img['data'] + self.stride * img['ph']])
        self.px = gim.unswizzle(px, self.stride, img['ph']) if img['order'] == 1 else bytearray(px)
        pd = pal['data']
        self.palette = [tuple(self.raw[pd + i * 4:pd + i * 4 + 4]) for i in range(pal['w'])]
        cand = [(i, c[3]) for i, c in enumerate(self.palette) if c[3] == 0 or c[:3] == (255, 255, 255)]
        zero = next(i for i, a in cand if a == 0)
        self.amap = [zero if v < 8 else min(cand, key=lambda ia: abs(ia[1] - v))[0] for v in range(256)]

    def get(self, x, y):
        if self.bpp == 8:
            return self.px[y * self.stride + x]
        v = self.px[y * self.stride + x // 2]
        return (v >> 4) if x & 1 else (v & 15)

    def put(self, x, y, v):
        if self.bpp == 8:
            self.px[y * self.stride + x] = v
            return
        o = y * self.stride + x // 2
        self.px[o] = ((self.px[o] & 0x0f) | (v << 4)) if x & 1 else ((self.px[o] & 0xf0) | v)

    def set_cell(self, slot, alpha, cell):
        per_row = self.w // cell
        x0, y0 = (slot % per_row) * cell, (slot // per_row) * cell
        for y in range(cell):
            for x in range(cell):
                self.put(x0 + x, y0 + y, self.amap[alpha[y][x]])

    def opaque_share(self):
        ink = full = 0
        for y in range(self.h):
            for x in range(self.w):
                a = self.palette[self.get(x, y)][3]
                if a:
                    ink += 1
                    full += a >= 0xf0
        return full / ink if ink else 0

    def to_bytes(self):
        img = self.img
        px = gim.swizzle(self.px, self.stride, img['ph']) if img['order'] == 1 else self.px
        self.raw[img['data']:img['data'] + len(px)] = px
        return bytes(self.raw)


def _atlases(names, base):
    out = []
    k = 0
    while f'{base}_{k:02d}.gim' in names:
        out.append(f'{base}_{k:02d}.gim')
        k += 1
    return out


def glyph(ch, bold, cell):
    size = round(15 * cell / 16)
    path = rutext.FONT_BOLD if bold else rutext.FONT_REGULAR
    alpha, _ = gimfont.render_prop(rutext.render_char(ch), path, size, cell=cell)
    return alpha


def build_font(items, lst_name, needed, keep_jp, cache):
    """Rewrite one font inside an archive (items: list of (name, hash, data)).
    needed: characters the Russian text needs; keep_jp: characters that must stay.
    cache: shared between copies of the same font (same input -> same output)."""
    names = {n: i for i, (n, _, _) in enumerate(items)}
    base, cell = FONTS[lst_name]
    gnames = _atlases(names, base)
    if not gnames:
        raise ValueError(f'no atlases for {lst_name}')
    li = names[lst_name]
    key = (lst_name, items[li][2], tuple(items[names[g]][2] for g in gnames), needed, frozenset(keep_jp))
    if key not in cache:
        chars = [c for c, _ in fontset.parse_lst(items[li][2])]
        atl = [Atlas(items[names[g]][2]) for g in gnames]
        per_atlas = (256 // cell) ** 2
        bold = atl[0].opaque_share() > 0.45
        cap = per_atlas * len(atl)
        missing = [c for c in dict.fromkeys(needed) if c not in chars]
        slots = list(range(len(chars), cap))
        droppable = [i for i, c in enumerate(chars)
                     if c not in keep_jp and c not in needed and not rutext.is_narrow(c) and c not in rutext.KEEP]
        free = slots + droppable
        if len(missing) > len(free):
            raise ValueError(f'{lst_name}: need {len(missing)} cells, only {len(free)} free')
        for c in missing:
            i = free.pop(0)
            if i < len(chars):
                chars[i] = c
            else:
                chars.append(c)
        for i, c in enumerate(chars):
            if rutext.is_narrow(c) or c in missing:
                atl[i // per_atlas].set_cell(i % per_atlas, glyph(c, bold, cell), cell)
        info = {'chars': len(chars), 'cap': cap, 'added': len(missing), 'bold': bold,
                'reused_jp': max(0, len(missing) - len(slots))}
        cache[key] = (fontset.dump_lst([(c, i) for i, c in enumerate(chars)]),
                      [a.to_bytes() for a in atl], info)
    new_lst, new_gims, info = cache[key]
    items[li] = (items[li][0], items[li][1], new_lst)
    for g, data in zip(gnames, new_gims):
        i = names[g]
        items[i] = (items[i][0], items[i][1], data)
    return info
