"""Add characters to a font (lst + atlases) inside XBB archives.

A font is a *_lst.txt ("char=index" per line) plus atlases <base>_00.gim,
<base>_01.gim ... (256 glyphs each, 16x16 cells). Every archive that holds a
copy of the font must get the same update.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gimfont  # noqa: E402
import rutext  # noqa: E402
import xbb  # noqa: E402


def parse_lst(data):
    out = []
    # "<char>=<n>" or just "<char>" per line; the game ignores '=', digits and line breaks
    for line in rutext.decode(data).splitlines():
        if line:
            ch = line.rsplit('=', 1)[0] if '=' in line[1:] else line
            out.append((ch, len(out)))
    return out


def dump_lst(items):
    return rutext.encode(''.join(f'{c}={i}\n' for c, i in items))


class _GimBytes(gimfont.Gim):
    def __init__(self, data):  # noqa: D107 - load from bytes instead of path
        self.raw = bytearray(data)
        self._find(0x10, len(self.raw))
        self.w, self.h = 256, 256
        self.stride = self.w // 2
        self.pix = self._unswizzle(bytes(self.raw[self.data_off:self.data_off + self.stride * self.h]))

    def to_bytes(self):
        self.raw[self.data_off:self.data_off + len(self.pix)] = self._swizzle(self.pix)
        return bytes(self.raw)


def add_chars(items, lst_name, atlas_base, chars, glyph=gimfont.render_glyph):
    """items: list of (name, hash, data) of an XBB archive (changed in place).
    Returns list of chars added."""
    names = {n: i for i, (n, _, _) in enumerate(items)}
    li = names[lst_name]
    lst = parse_lst(items[li][2])
    known = {c for c, _ in lst}
    nxt = max(i for _, i in lst) + 1
    added = []
    atlases = {}
    for ch in chars:
        if ch in known or ch in '\n':
            continue
        atlas, slot = divmod(nxt, 256)
        an = f'{atlas_base}_{atlas:02d}.gim'
        if an not in names:
            raise ValueError(f'{an} not in archive: font {lst_name} is full')
        if an not in atlases:
            atlases[an] = _GimBytes(items[names[an]][2])
        atlases[an].set_cell(slot, glyph(ch))
        lst.append((ch, nxt))
        known.add(ch)
        added.append(ch)
        nxt += 1
    for an, g in atlases.items():
        i = names[an]
        items[i] = (items[i][0], items[i][1], g.to_bytes())
    items[li] = (items[li][0], items[li][1], dump_lst(lst))
    return added


def patch_archive(src, dst, fonts):
    """fonts: list of (lst_name, atlas_base, chars)."""
    d, gz = xbb.load(src)
    items = [(e['name'], e['hash'], d[e['off']:e['off'] + e['size']]) for e in xbb.parse(d)]
    for lst_name, base, chars in fonts:
        added = add_chars(items, lst_name, base, chars)
        print(f'  {os.path.basename(src)}: {lst_name} +{len(added)}')
    out = xbb.build(items)
    xbb.save(dst, out, gz, os.path.basename(src))
