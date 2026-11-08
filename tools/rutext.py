"""Russian text -> what the game can print.

The renderer looks every character up as a 2-byte Shift-JIS code, except the
ASCII space (half a cell, uses no sprite) and newline. So ASCII punctuation,
digits and Latin letters become their full-width forms; the proportional width
table makes them narrow again.
"""
import os

from PIL import ImageFont

import gimfont

CYRILLIC = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя'

_FW = {chr(c): chr(c + 0xFEE0) for c in range(0x21, 0x7F)}
_FW.update({'-': '－', '~': '～', "'": '’', '"': '”', '\\': '＼'})
_FW_BACK = {v: k for k, v in _FW.items()}
_FW_BACK.update({'。': '.', '、': ',', '・': '·', '…': '…', '‥': '‥', '「': '«', '」': '»',
                 '『': '«', '』': '»', '“': '«', '”': '»', '～': '~', '’': "'"})


def to_game(text):
    """Normalize Russian text for the game (keeps \\n and ASCII spaces)."""
    out = []
    for ch in text:
        if ch in ' \n':
            out.append(ch)
        elif ch == '«':
            out.append('「')
        elif ch == '»':
            out.append('」')
        elif ch == '—' or ch == '–':
            out.append('－')
        elif ch in _FW:
            out.append(_FW[ch])
        else:
            out.append(ch)
    s = ''.join(out)
    s.encode('cp932')  # raises if something cannot be printed
    return s


def render_char(ch):
    """Character actually drawn into the atlas for a game character."""
    return _FW_BACK.get(ch, ch)


def is_narrow(ch):
    """Characters that get a proportional width."""
    try:
        b = ch.encode('cp932')
    except UnicodeEncodeError:
        return False
    return len(b) == 2 and b[0] in (0x84, 0x81, 0x82) and ch not in '　'


FONT_REGULAR = r'C:\Windows\Fonts\YuGothM.ttc'
FONT_BOLD = r'C:\Windows\Fonts\YuGothB.ttc'


def glyph(ch, bold=False, size=15):
    """(alpha rows, advance) for a narrow character."""
    path = FONT_BOLD if bold else FONT_REGULAR
    c = render_char(ch)
    if c in '「」':
        c = {'「': '«', '」': '»'}[c]
    alpha, adv = gimfont.render_prop(c, path, size)
    return alpha, adv


def width_table(bold=False, size=15):
    """{cp932 code: advance px} for all Russian letters and narrow symbols."""
    chars = CYRILLIC + ''.join(_FW.values()) + '「」・、。'
    out = {}
    for ch in chars:
        if not is_narrow(ch):
            continue
        _, adv = glyph(ch, bold, size)
        out[int.from_bytes(ch.encode('cp932'), 'big')] = adv
    return out
