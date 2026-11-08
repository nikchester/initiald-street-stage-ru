"""Text files inside archives: card viewer descriptions, Project D homepage.

PARTS maps an archive (relative to data/) to a function(items) that rewrites
its text files in place and returns (pairs [(jp, game text)], missing count).
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import rutext  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTHS = None


def widths():
    global WIDTHS
    if WIDTHS is None:
        WIDTHS = rutext.width_table()
    return WIDTHS


def text_px(s):
    w = widths()
    return sum(6 if c == ' ' else w.get(rutext.code(c), 16) for c in rutext.to_game(s))


def wrap(text, max_px):
    """Wrap Russian text at spaces so every line fits max_px."""
    out = []
    for para in text.split('\n'):
        line = ''
        for word in para.split(' '):
            cand = word if not line else line + ' ' + word
            if line and text_px(cand) > max_px:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line)
    return out


def load(prefix):
    tr = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'text', prefix + '*.json'))):
        for k, v in json.load(open(path, encoding='utf-8')).items():
            if not k.startswith('_'):
                tr[k] = v
    return tr


# ---------------------------------------------------------------- cards
CARD_PX = 284          # 18 full-width cells minus a margin
CARD_LINES = 8
CARD_GLYPHS = 170      # one font object draws at most 176 sprites

X_NAMES = {
    '藤原拓海': 'Такуми Фудзивара', '高橋啓介': 'Кэйсукэ Такахаси', '高橋涼介': 'Рёсукэ Такахаси',
    '武内樹': 'Ицуки Такэути', '池谷浩一郎': 'Коитиро Икэтани', '健二': 'Кэндзи', '中里毅': 'Такэси Накадзато',
    '庄司慎吾': 'Синго Сёдзи', '佐藤真子＆沙雪': 'Мако Сато и Саюки', '中村賢太': 'Кэнта Накамура',
    '須藤京一': 'Кёити Судо', '岩城清次': 'Сэйдзи Иваки', '秋山渉': 'Ватару Акияма', '小柏カイ': 'Кай Когасива',
    '末次トオル': 'Тоору Суэцугу', '川井淳郎': 'Ацуро Каваи', '二宮大輝': 'Дайки Ниномия',
    'スマイリー酒井': 'Смайли Сакаи', '舘智幸': 'Томоюки Тати', '東京から来た二人': 'Двое из Токио',
    '岩瀬恭子': 'Кёко Ивасэ', '秋山延彦': 'Нобухико Акияма', '坂本': 'Сакамото',
    'ランエボⅤの男': 'Парень на Evo V', 'ランエボⅥの男': 'Парень на Evo VI',
    '藤原拓海（プロジェクトＤ）': 'Такуми Фудзивара (Project D)', '高橋啓介（プロジェクトＤ）': 'Кэйсукэ Такахаси (Project D)',
    '高橋涼介（プロジェクトＤ）': 'Рёсукэ Такахаси (Project D)', '藤原文太': 'Бунта Фудзивара',
    '佐藤真子': 'Мако Сато', '沙雪': 'Саюки',
}
COURSES = {'妙義': 'Мёги', '碓氷': 'Усуи', '赤城': 'Акаги', '秋名': 'Акина', 'いろは坂': 'Ироха',
           '八方ヶ原': 'Хаппо', '正丸': 'Сёмару', '土坂': 'Цутисака'}


def card_info(jp):
    j = jp.replace('\r\n', '')
    m = re.search(r'「(.*?)」', j)
    x = m.group(1) if m else ''
    if j.startswith('通信対戦で、ライバル車'):
        return f'В сетевой гонке теперь\nможно выбрать машину:\n«{X_NAMES[x]}».'
    if 'ボイスが聞けるように' in j:
        return f'На сайте Project D теперь\nможно послушать голос:\n«{X_NAMES[x]}».'
    if 'ダウンロード可能' in j:
        num = re.sub(r'\D', '', x.translate({c: c - 0xFEE0 for c in range(0xFF10, 0xFF1A)}))
        return f'На сайте Project D теперь\nможно скачать «BGM № {num}».'
    if j.startswith('ローディング画面のバリエーション'):
        return 'Добавлен новый фон экрана\nзагрузки.\n\nЕго можно посмотреть\nв галерее сайта Project D.'
    m = re.match(r'プロジェクトＤホームページで(.+?)のコース解説', j)
    if m:
        return f'На сайте Project D открыт\nразбор трассы {COURSES[m.group(1)]}.'
    return None


def apply_cards(items):
    tr = load('cards_ru_')
    pairs, missing, warn = [], 0, []
    for k, (name, h, data) in enumerate(items):
        if name != 'cardtext.txt':
            continue
        text = data.decode('cp932')
        head, body = text.split('[START]', 1)
        blocks = re.split(r'(//-{10,}\r\n)', body)
        out = [head, '[START]']
        for blk in blocks:
            m = re.match(r'// (\d+)', blk)
            if not m:
                out.append(blk)
                continue
            num = m.group(1)
            t = tr.get(num)
            if t is None:
                missing += 1
                out.append(blk)
                continue

            def repl(tag, end, new, blk=blk):
                mm = re.search(r'(\[' + tag + r'\]\r\n)(.*?)(\[' + end + r'\])', blk, re.S)
                if not mm or new is None:
                    return blk
                jp = mm.group(2)
                lines = wrap(new, CARD_PX)
                g = rutext.to_game('\n'.join(lines))
                pairs.append((jp, g))
                if tag == 'TEXT':
                    glyphs = sum(1 for c in g if c not in ' \n')
                    if len(lines) > CARD_LINES or glyphs > CARD_GLYPHS:
                        warn.append(f'card {num}: {len(lines)} lines, {glyphs} glyphs')
                return blk[:mm.start(2)] + g.replace('\n', '\r\n') + '\r\n' + blk[mm.end(2):]
            jp_info = re.search(r'\[INFO\]\r\n(.*?)\[INFOEND\]', blk, re.S)
            info = t.get('I') or (card_info(jp_info.group(1)) if jp_info and jp_info.group(1).strip() else None)
            blk = repl('INFO', 'INFOEND', info)
            blk = repl('HINT', 'HINTEND', t.get('H'), blk=blk)
            blk = repl('TEXT', 'END', t.get('T'), blk=blk)
            out.append(blk)
        items[k] = (name, h, rutext.encode(''.join(out)))
    for w in warn:
        print('  WARNING', w)
    return pairs, missing


# ---------------------------------------------------------------- homepage
HP_PX = 270
HP_SECTIONS = {'GALLERY', 'BGM', 'VOICE', 'COURSE', 'MOVIE', 'RECORD'}
HP_FIELDS = {'NAME', 'INTRODUCTION', 'CAPTURE', 'CAPTURE_POINT'}
FW_DIGITS = {c: c - 0xFEE0 for c in range(0xFF10, 0xFF1A)}


def _num(s):
    return s.translate(FW_DIGITS)


def gallery_name(jp):
    m = re.fullmatch(r'(新規)?ローディング画像([０-９]+)', jp)
    if not m:
        return None
    return ('Новый экран загрузки ' if m.group(1) else 'Экран загрузки ') + _num(m.group(2))


def gallery_intro(jp):
    j = jp.replace('\r\n', '').replace('\\n', '')
    m = re.match(r'ローディング画面の壁紙バリエーション([０-９]+)。(?:カード№([０-９]+)を入手で閲覧可能。)?', j)
    if not m:
        return None
    s = f'Фон экрана загрузки,\nвариант {_num(m.group(1))}.'
    if m.group(2):
        s += f'\n\nОткрывается картой\n№ {_num(m.group(2))}.'
    return s


def apply_homepage(items):
    tr = load('hp_ru')
    pairs, missing = [], 0
    for k, (name, h, data) in enumerate(items):
        if name == 'homepagedata.txt':
            # the original mixes CRLF and LF; the game accepts both
            lines = data.decode('cp932').replace('\r\n', '\n').split('\n')
            out, sec, ident, i, cp = [], None, None, 0, 0
            while i < len(lines):
                line = lines[i]
                tag = re.fullmatch(r'\[(\w+)\]', line)
                if tag and tag.group(1) in HP_SECTIONS:
                    sec = tag.group(1)
                elif tag and tag.group(1) == 'ID':
                    out.append(line)
                    i += 1
                    ident = lines[i]
                    cp = 0
                    line = lines[i]
                elif tag and tag.group(1) in HP_FIELDS:
                    field = tag.group(1)
                    out.append(line)
                    i += 1
                    body = []
                    if field == 'NAME':
                        body = [lines[i]]
                        i += 1
                    else:
                        while i < len(lines):
                            body.append(lines[i])
                            i += 1
                            if body[-1].endswith('/'):
                                break
                    jp = '\r\n'.join(body)
                    key = f'{sec}/{ident}/{field}' + (f'/{cp}' if field == 'CAPTURE_POINT' else '')
                    if field == 'CAPTURE_POINT':
                        cp += 1
                    ru = tr.get(key)
                    if ru is None and sec == 'GALLERY':
                        ru = gallery_name(jp) if field == 'NAME' else gallery_intro(jp)
                    if ru is None and sec == 'VOICE' and field == 'NAME':
                        ru = X_NAMES.get(jp)
                    if ru is None:
                        if sec != 'BGM':
                            missing += 1
                        out.extend(body)
                        continue
                    new = [ru] if field == 'NAME' else wrap(ru, HP_PX)
                    g = rutext.to_game('\r\n'.join(new) + ('/' if jp.endswith('/') else ''))
                    pairs.append((jp, g))
                    out.append(g)
                    continue
                out.append(line)
                i += 1
            items[k] = (name, h, rutext.encode('\r\n'.join(out)))
        elif name == 'gallery_historytext.txt':
            out = []
            for line in re.split(r'(\r\n|\n)', data.decode('cp932')):   # mixed CRLF / LF
                ru = gallery_name(line) or gallery_intro(line)
                if ru:
                    g = rutext.to_game(ru).replace('\n', '\\n')
                    pairs.append((line, g))
                    line = g
                out.append(line)
            items[k] = (name, h, rutext.encode(''.join(out)))
    return pairs, missing


PARTS = {
    'card/view/card_viewer.bin': apply_cards,
    'homepage/hp_data_00.bin.gz': apply_homepage,
}
