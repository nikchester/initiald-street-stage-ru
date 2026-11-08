"""Contact sheets of candidate images (work/png/all/cand.json) -> work/png/sheets/NN.png"""
import json
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = os.path.join(ROOT, 'work', 'png', 'all')
OUT = os.path.join(ROOT, 'work', 'png', 'sheets')
MAX_H = 1900


def main():
    os.makedirs(OUT, exist_ok=True)
    cand = json.load(open(os.path.join(ALL, 'cand.json')))
    order = sorted(cand, key=lambda k: (cand[k]['where'][0][0], cand[k]['where'][0][1]))
    order = [k for k in order if cand[k]['size'][0] * cand[k]['size'][1] > 32 * 32]
    sheets, cur, h = [], [], 0
    for k in order:
        im = Image.open(os.path.join(ALL, k + '.png')).convert('RGBA')
        if im.width > 512:
            im = im.resize((512, im.height * 512 // im.width))
        if im.height >= 128:   # large pictures: half size is enough to spot text
            im = im.resize((im.width // 2, im.height // 2))
        need = im.height + 12
        if cur and h + need > MAX_H:
            sheets.append(cur)
            cur, h = [], 0
        cur.append((k, im))
        h += need
    if cur:
        sheets.append(cur)
    listing = []
    for n, items in enumerate(sheets):
        H = sum(im.height + 12 for _, im in items)
        sheet = Image.new('RGB', (512, H), (70, 70, 95))
        dr = ImageDraw.Draw(sheet)
        y = 0
        for k, im in items:
            w = cand[k]['where'][0]
            dr.text((2, y), f'{k} {w[0].split("/")[-1][:22]} {w[1][-22:]} {cand[k]["size"]}', fill=(255, 255, 0))
            sheet.paste(im, (0, y + 11), im)
            y += im.height + 12
            listing.append((n, k))
        sheet.save(os.path.join(OUT, f'{n:02d}.png'))
    print(len(sheets), 'sheets,', len(listing), 'images')


if __name__ == '__main__':
    main()
