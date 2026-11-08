"""Make a labelled contact sheet from a folder of PNGs: python contact.py <dir> <out.png> [filter]"""
import os
import sys

from PIL import Image, ImageDraw

src, out = sys.argv[1], sys.argv[2]
flt = sys.argv[3] if len(sys.argv) > 3 else ''
files = sorted(f for f in os.listdir(src) if f.endswith('.png') and flt in f)
ims = [(f, Image.open(os.path.join(src, f)).convert('RGBA')) for f in files]
W = max(i.width for _, i in ims)
H = sum(i.height + 14 for _, i in ims)
sheet = Image.new('RGB', (W, H), (60, 60, 80))
dr = ImageDraw.Draw(sheet)
y = 0
for f, im in ims:
    dr.text((2, y), f, fill=(255, 255, 0))
    sheet.paste(im, (0, y + 13), im)
    y += im.height + 14
sheet.save(out)
print(out, W, H)
