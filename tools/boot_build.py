"""Apply text/boot_ru_*.json to BOOT.BIN.

Translation files map string vaddr (hex) -> Russian text. A translation is
copied to every other string with the same Japanese text. '@charset' marks a
lecture "character set" string; it is rebuilt from the lines its table lists.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bootpatch  # noqa: E402
import extract_boot  # noqa: E402
import prx  # noqa: E402
import rutext  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP_CHARS = re.compile(r'[぀-ヿ一-鿿]')
MAX_LINE_PX = 390
NG_WORDS = (0x211fc4, 0x212bc0)   # name filter list, never displayed
NAMES = (0x21d6b0, 0x21dae0)      # default driver names, drawn with the player-name font


def load_translations():
    tr = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'text', 'boot_ru_*.json'))):
        for k, v in json.load(open(path, encoding='utf-8')).items():
            if not k.startswith('_'):
                tr[k] = v
    return tr


def line_px(line, widths):
    px = 0
    for ch in line:
        if ch == ' ':
            px += 6
            continue
        code = rutext.code(ch)
        px += widths.get(code, 16)
    return px


def build(boot):
    p = prx.Prx(boot)
    refs = p.references()
    items = extract_boot.extract(boot)
    jp_by_id = {i['id']: i['jp'] for i in items}
    tr = load_translations()
    unknown = [k for k in tr if k not in jp_by_id]
    by_jp = {}
    for k, v in tr.items():
        if k in jp_by_id:
            by_jp.setdefault(jp_by_id[k], v)
    final = {}
    for i in items:
        if i['jp'] in by_jp:
            final[i['id']] = by_jp[i['jp']]
    # character sets of lecture tips
    for k, v in list(final.items()):
        if v != '@charset':
            continue
        w = refs[int(k, 16)][0][1]
        chars = ''
        for n in range(1, 4):
            t = f'{p.word(w + 4 * n):06x}'
            if t in final and final[t] != '@charset':
                chars += final[t]
        final[k] = ''.join(dict.fromkeys(c for c in chars if c not in ' \n')) or ' '
    widths = rutext.width_table()
    strings, warnings, pairs = [], [], []
    for k, v in final.items():
        g = rutext.to_game(v)
        pairs.append((jp_by_id[k], g))
        for line in g.split('\n'):
            px = line_px(line, widths)
            if px > MAX_LINE_PX and not jp_by_id[k].startswith(('そのクルマ',)):
                warnings.append(f'{k}: {px}px: {line}')
        strings.append((int(k, 16), g))
    new_boot, rep = bootpatch.build(boot, strings, widths)
    remaining_jp = []          # untranslated strings that may still be shown
    for i in items:
        va = int(i['id'], 16)
        if (i['id'] in final or NG_WORDS[0] <= va < NG_WORDS[1] or NAMES[0] <= va < NAMES[1]
                or len(i['jp']) <= 1):
            continue
        remaining_jp.append(i['jp'])
    rep.update({'translated': len(final), 'total': len(items), 'unknown_ids': unknown})
    return new_boot, rep, warnings, pairs, remaining_jp


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    boot = open(os.path.join(ROOT, 'extracted', 'PSP_GAME', 'SYSDIR', 'BOOT.BIN'), 'rb').read()
    new, rep, warn, used, rem = build(boot)
    print(rep)
    for w in warn:
        print('WIDE', w)
