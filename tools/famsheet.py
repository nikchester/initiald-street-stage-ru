"""Contact sheet of candidate images whose name contains a pattern.
  python famsheet.py <regex> <out.png> [scale]"""
import json
import os
import re
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = os.path.join(ROOT, 'work', 'png', 'all')
cand = json.load(open(os.path.join(ALL, 'cand.json')))
pat = re.compile(sys.argv[1])
scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1
keys = sorted((k for k, v in cand.items() if any(pat.search(w[0] + '/' + w[1]) for w in v['where'])),
              key=lambda k: cand[k]['where'][0])
ims = []
for k in keys:
    im = Image.open(os.path.join(ALL, k + '.png')).convert('RGBA')
    if scale != 1:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
    ims.append((k, im))
H = sum(im.height + 12 for _, im in ims) or 1
sheet = Image.new('RGB', (max([512] + [im.width for _, im in ims]), H), (70, 70, 95))
dr = ImageDraw.Draw(sheet)
y = 0
for k, im in ims:
    w = cand[k]['where'][0]
    dr.text((2, y), f'{k} {w[0].split("/")[-1][:20]} {w[1][-24:]} {cand[k]["size"]} x{len(cand[k]["where"])}', fill=(255, 255, 0))
    sheet.paste(im, (0, y + 11), im)
    y += im.height + 12
sheet.save(sys.argv[2])
print(len(ims), sheet.size)
