"""Russian text -> bytes the game can print.

The renderer looks every character up as a 2-byte code in the font list,
except the ASCII space (a narrow gap, uses no sprite) and newline.

Shift-JIS page 0x84 holds the Cyrillic alphabet. The rest of that page is
unused by the game, so Russian punctuation, digits and Latin letters get
private codes there (0x84 0x92..0xFC). Inside Python such a character is the
private-use code point U+F0000 + trail byte. The proportional width table in
BOOT.BIN covers page 0x84 only, so Japanese text keeps its full-width look.
"""
import gimfont

CYRILLIC = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя'
NARROW_SYMBOLS = ('.,!?:;-()«»"\'/%+&*=~#[]<>_…'
                  '0123456789'
                  'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                  'abcdefghijklmnopqrstuvwxyz')
_TRAILS = [t for t in range(0x92, 0xFD)]
assert len(NARROW_SYMBOLS) <= len(_TRAILS)
PUA = 0xF0000
SYM2PUA = {s: chr(PUA + t) for s, t in zip(NARROW_SYMBOLS, _TRAILS)}
PUA2SYM = {v: k for k, v in SYM2PUA.items()}
# characters of the original fonts the game keeps using in Russian text
KEEP = set('凜熙')   # ○ / × button icons

_ALIASES = {'—': '-', '–': '-', '·': '.', '“': '«', '”': '»', '„': '«', '’': "'", '‘': "'",
            '！': '!', '？': '?', '，': ',', '．': '.', '：': ':', '％': '%', '／': '/', '－': '-'}


def to_game(text):
    """Normalize Russian text: narrow symbols -> private characters."""
    out = []
    for ch in text:
        ch = _ALIASES.get(ch, ch)
        if ch in ' \n' or ch in KEEP:
            out.append(ch)
        elif ch in SYM2PUA:
            out.append(SYM2PUA[ch])
        else:
            out.append(ch)
    s = ''.join(out)
    encode(s)   # raises if something cannot be printed
    return s


def encode(s):
    b = bytearray()
    for ch in s:
        o = ord(ch)
        if o >= PUA:
            b += bytes((0x84, o - PUA))
        else:
            b += ch.encode('cp932')
    return bytes(b)


def decode(b):
    out = []
    i = 0
    while i < len(b):
        c = b[i]
        if c == 0x84 and i + 1 < len(b) and b[i + 1] in _TRAILS:
            out.append(chr(PUA + b[i + 1]))
            i += 2
        elif 0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc:
            out.append(b[i:i + 2].decode('cp932', 'replace'))
            i += 2
        else:
            out.append(chr(c))
            i += 1
    return ''.join(out)


def code(ch):
    return int.from_bytes(encode(ch), 'big')


def is_narrow(ch):
    return ch in CYRILLIC or ch in PUA2SYM


def render_char(ch):
    return PUA2SYM.get(ch, ch)


FONT_REGULAR = r'C:\Windows\Fonts\YuGothM.ttc'
FONT_BOLD = r'C:\Windows\Fonts\YuGothB.ttc'


def glyph(ch, bold=False, size=15):
    """(alpha rows, advance) for a narrow character (16 px cell)."""
    path = FONT_BOLD if bold else FONT_REGULAR
    return gimfont.render_prop(render_char(ch), path, size)


def width_table(bold=False, size=15):
    """{2-byte code: advance px (16 px cell)} for every narrow character."""
    out = {}
    for ch in list(CYRILLIC) + list(PUA2SYM):
        _, adv = glyph(ch, bold, size)
        out[code(ch)] = adv
    return out
