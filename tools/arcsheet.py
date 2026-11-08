"""Sheets of remaining candidates (cand2.json) for archives matching a regex.
  python arcsheet.py <regex> <prefix> [scale]  -> <prefix>_N.png (1400 px tall parts)"""
import json
import os
import re
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = os.path.join(ROOT, 'work', 'png', 'all')
cand = json.load(open(os.path.join(ALL, 'cand2.json')))
pat = re.compile(sys.argv[1])
scale = float(sys.argv[3]) if len(sys.argv) > 3 else 0.75
keys = sorted((k for k, v in cand.items() if pat.search(v['where'][0][0])), key=lambda k: cand[k]['where'][0])
parts, cur, h = [], [], 0
for k in keys:
    im = Image.open(os.path.join(ALL, k + '.png')).convert('RGBA')
    s = scale if im.height < 128 else scale * 0.6
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))
    if cur and h + im.height + 12 > 1400:
        parts.append(cur)
        cur, h = [], 0
    cur.append((k, im))
    h += im.height + 12
if cur:
    parts.append(cur)
for n, items in enumerate(parts):
    H = sum(im.height + 12 for _, im in items)
    sheet = Image.new('RGB', (512, H), (70, 70, 95))
    dr = ImageDraw.Draw(sheet)
    y = 0
    for k, im in items:
        w = cand[k]['where'][0]
        dr.text((2, y), f'{k} {w[1][-26:]} {cand[k]["size"]}', fill=(255, 255, 0))
        sheet.paste(im, (0, y + 11), im)
        y += im.height + 12
    sheet.save(f'{sys.argv[2]}_{n}.png')
print(len(keys), 'images,', len(parts), 'parts')
