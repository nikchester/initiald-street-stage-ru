"""Russian graphics for the game mode select screen (select/sel_gamemode.bin.gz).

Reads original PNGs from work/png/sel_gamemode (made by `gim.py dump`)
and writes replacements to work/ru/sel_gamemode with the same names.
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import art  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'png', 'sel_gamemode')
DST = os.path.join(ROOT, 'work', 'ru', 'sel_gamemode')
P = 'PSP_mode_select.ana__{:02d}_PSP_{}.png'


def src(i, kind='mod'):
    return Image.open(os.path.join(SRC, P.format(i, kind))).convert('RGBA')


def save(im, i, kind='mod'):
    im.save(os.path.join(DST, P.format(i, kind)))


# --- big titles: (plain, glow only, glow + text), segments (text, red accent, scale)
TITLES = [
    ((6, 9, 12), [('ВЫЗОВ ', False, 1), ('Б', True, 1), ('УНТЕ!!', False, 1)]),
    ((7, 10, 13), [('ЛЕГЕНДА ', False, 1), ('Д', True, 1), ('ОРОГ', False, 1)]),
    ((8, 11, 14), [('ЗАЕЗД ', False, 1), ('Н', True, 1), ('А ВРЕМЯ', False, 1)]),
    ((25, 30, 35), [('СВ', False, 1), ('Я', True, 1), ('ЗЬ', False, 1)]),
    ((26, 31, 36), [('ГА', False, 1), ('Р', True, 1), ('АЖ', False, 1)]),
    ((27, 32, 37), [('КОЛЛЕКЦИЯ ', False, 1), ('К', True, 1), ('АРТ', False, 1)]),
    ((28, 33, 38), [('САЙТ ПРОЕКТА ', False, 0.75), ('D', True, 1.25)]),
    ((29, 34, 39), [('НАСТ', False, 1), ('Р', True, 1), ('ОЙКИ', False, 1)]),
]

DESCR = {
    15: ['Настоящая битва с Бунтой Фудзиварой!!',
         'Сможешь ли ты победить сильнейшего и быстрейшего?!'],
    16: ['Отправляйся на перевалы и сражайся с соперниками!!',
         'Побеждай одного за другим и стань самым быстрым!!'],
    17: ['Режим заезда в одиночку на лучшее время.',
         'Время можно занести в раздел «Рекорды»',
         'на «Сайте Проекта D».'],
    40: ['Игра с другими игроками по беспроводной связи:',
         '«Бой» «Обмен картами и повторами» «Сравнение рекордов»'],
    41: ['Тюнинг машин из гаража картами, собранными в гонках.',
         'Здесь же можно добавить машину в гараж',
         'или удалить её.'],
    42: ['Просмотр карт, собранных в гонках и при обмене.',
         'Описания на картах расскажут о мире Initial D.'],
    43: ['На сайте есть 6 разделов:',
         '«Галерея» «Звуки» «Трассы» «Видео» «Повторы» «Рекорды»'],
    44: ['Изменение настроек, сохранение и загрузка данных игры.'],
}


def title_box(im, min_w=300):
    x0, y0, x1, y1 = im.getchannel('A').getbbox()
    cx = (x0 + x1) // 2
    w = max(min_w, x1 - x0)
    a = max(4, cx - w // 2)
    b = min(im.width - 4, a + w)
    return (a, y0 - 2, b, y1 + 2)


def header():
    im = src(0, 'ups')
    art.column_fill(im, 5, (6, 0, 480, 29))
    t = 'ВЫБЕРИТЕ РЕЖИМ ИГРЫ'
    f = art.fit_font(art.HEAD_FONT, t, 380, 17)
    dr = ImageDraw.Draw(im)
    l, top, r, b = dr.textbbox((0, 0), t, font=f)
    x = (480 - (r - l)) / 2 - l
    y = 4 + (20 - (b - top)) / 2 - top   # original glyphs occupy rows 4..24
    dr.text((x + 2, y + 2), t, font=f, fill=(60, 0, 0, 255))
    dr.text((x, y), t, font=f, fill=art.WHITE)
    save(im, 0, 'ups')


def footer():
    im = src(1, 'ups')
    for box, dx in (((167, 1, 206, 17), 60), ((231, 1, 270, 17), 124), ((301, 1, 350, 17), 200)):
        art.pattern_fill(im, box, 4, dx)
    f = art.font(art.SMALL_FONT, 10)
    dr = ImageDraw.Draw(im)
    for x, t in ((170, 'Выбор'), (234, 'ОК'), (304, 'Назад')):
        dr.text((x, 3), t, font=f, fill=(252, 163, 7, 255))
    save(im, 1, 'ups')


def panel_label():
    """Label 'ゲームの内容' on the description panel -> 'Описание режима'."""
    im = src(2)
    art.column_fill(im, 74, (79, 11, 168, 28))
    t = 'Описание режима'
    f = art.font(art.SMALL_FONT, 9)
    dr = ImageDraw.Draw(im)
    w = dr.textlength(t, font=f)
    dr.rounded_rectangle((81, 13, 81 + w + 14, 25), radius=6, fill=(34, 45, 76, 255), outline=(77, 88, 111, 255))
    dr.text((88, 14), t, font=f, fill=art.WHITE)
    save(im, 2)


def main():
    os.makedirs(DST, exist_ok=True)
    header()
    footer()
    panel_label()
    for (plain, glow, glow_text), seg in TITLES:
        box = title_box(src(plain))
        size = src(plain).size
        save(art.render_title(size, seg, box), plain)
        save(art.render_title(size, seg, box, glow=True, text=False), glow)
        save(art.render_title(size, seg, box, glow=True, text=True), glow_text)
    for i, lines in DESCR.items():
        save(art.render_lines(src(i).size, lines), i)
    print('written to', DST)


if __name__ == '__main__':
    main()
