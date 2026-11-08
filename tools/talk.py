"""Rival dialogue scripts (rivaldemo.bin.gz -> talkTbl_*.txt).

A script is a list of quoted lines, CRLF separated. Text lines contain Japanese;
everything else ("W_0", "N", "C_1", "M" ...) is a command. "\\n" inside a text
line is a literal backslash + n (line break in the window), "N" = next page,
"M" = the player's car name.

Translations: text/talk_ru_*.json, key = uid(jp) (first 10 hex of md5 of the
cp932 bytes), value = Russian text where "\\n" (a real newline in JSON) is a
line break. A trailing break of the original is kept automatically.

  python talk.py extract     -> work/text/talk_jp.txt (scene by scene, new lines only)
"""
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import rutext  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP = re.compile(r'[぀-ヿ一-鿿]')
BS_N = '\\n'   # literal backslash-n used by the scripts


def uid(jp):
    return hashlib.md5(jp.encode('cp932')).hexdigest()[:10]


def is_text(s):
    return bool(JP.search(s)) or s.startswith('‥') or s.startswith('…')


def parse(data):
    return data.decode('cp932').split('\r\n')


def load_translations(prefix='talk_ru_'):
    tr = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'text', prefix + '*.json'))):
        for k, v in json.load(open(path, encoding='utf-8')).items():
            if not k.startswith('_'):
                tr[k] = v
    return tr


def translate_line(jp, ru):
    """Russian line in script form (literal \\n, private codes)."""
    ends = jp.endswith(BS_N)
    ru = ru.rstrip('\n')
    g = rutext.to_game(ru).replace('\n', BS_N)
    if ends:
        g += BS_N
    return g


NAMES = {
    'イツキ': 'Ицуки', '健二': 'Кэндзи', '慎吾': 'Синго', 'トオル': 'Тоору', '淳郎': 'Ацуро',
    '真子': 'Мако', '沙雪': 'Саюки', 'デブ': 'Толстяк', 'メガネ': 'Очкарик', '賢太': 'Кэнта',
    '啓介': 'Кэйсукэ', '池谷': 'Икэтани', '中里': 'Накадзато', '京一': 'Кёити', '涼介': 'Рёсукэ',
    '拓海': 'Такуми', '文太': 'Бунта', '清次': 'Сэйдзи', 'カイ': 'Кай', '大輝': 'Дайки',
    '酒井': 'Сакаи', 'トモ': 'Томо', '延彦': 'Нобухико', '坂本': 'Сакамото', '渉': 'Ватару',
    '恭子': 'Кёко', 'エボⅤの男': 'Парень на Evo V', 'エボⅥの男': 'Парень на Evo VI',
    '史浩': 'Фумихиро', '松本': 'Мацумото',
}


def apply(items, tr):
    """Translate talk scripts and the speaker name table inside rivaldemo items.
    Returns (pairs [(jp, game_ru)], missing count)."""
    pairs, missing = [], 0
    for k, (name, h, data) in enumerate(items):
        if name.startswith('talkTbl_'):
            out = []
            for line in parse(data):
                m = re.fullmatch(r'"(.*)"', line)
                if m and is_text(m.group(1)):
                    jp = m.group(1)
                    ru = tr.get(uid(jp))
                    if ru is None:
                        missing += 1
                    else:
                        g = translate_line(jp, ru)
                        pairs.append((jp, g))
                        line = '"' + g + '"'
                out.append(line)
            items[k] = (name, h, rutext.encode('\r\n'.join(out)))
        elif name == 'charNameTbl.txt':
            out = []
            for line in parse(data):
                key = line.replace('　', '').rstrip('：')
                if key in NAMES:
                    g = rutext.to_game(NAMES[key] + ':')
                    pairs.append((line, g))
                    line = g
                out.append(line)
            items[k] = (name, h, rutext.encode('\r\n'.join(out)))
    return pairs, missing


def extract(items):
    """Text of all scripts, scene by scene; each new line once: 'uid|jp'."""
    seen = set()
    out = []
    for name, _, data in items:
        if not name.startswith('talkTbl_'):
            continue
        block = []
        for line in parse(data):
            m = re.fullmatch(r'"(.*)"', line)
            if not m:
                continue
            s = m.group(1)
            if is_text(s):
                u = uid(s)
                if u not in seen:
                    seen.add(u)
                    block.append(f'{u}|{s}')
            elif s.startswith('C_'):
                block.append(f'  [{s}]')
            elif s == 'M':
                block.append('  [CAR]')
        if any('|' in b for b in block):
            out.append(f'## {name[8:-4]}')
            out.extend(block)
    return out


if __name__ == '__main__':
    import xbb
    sys.stdout.reconfigure(encoding='utf-8')
    d, _ = xbb.load(os.path.join(ROOT, 'extracted', 'PSP_GAME', 'USRDIR', 'data', 'rivaldemo', 'rivaldemo.bin.gz'))
    items = [(e['name'], e['hash'], d[e['off']:e['off'] + e['size']]) for e in xbb.parse(d)]
    lines = extract(items)
    path = os.path.join(ROOT, 'work', 'text', 'talk_jp.txt')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(len([x for x in lines if '|' in x]), 'unique lines ->', path)
