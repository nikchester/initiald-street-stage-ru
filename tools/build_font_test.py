"""Font test build: put Cyrillic glyphs into the free cells of
rivaltalkfont_03.gim, add them to rivaltalkfont_lst.txt and replace every
dialogue line in rival talk scripts with a Russian test phrase.

  python build_font_test.py   (run from the project root)
"""
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gimfont  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'rivaldemo')
DST = os.path.join(ROOT, 'work', 'rivaldemo_fonttest')
ISO_IN = os.path.join(ROOT, 'Initital_D_Street_Stage_JAP_PSP-DMU.iso')
ISO_OUT = os.path.join(ROOT, 'build', 'InitialD_fonttest.iso')

CYR = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя'
FULL = 'Тест　шрифта！\\n'
PART = 'Да‥'

shutil.rmtree(DST, ignore_errors=True)
shutil.copytree(SRC, DST)

# 1. glyphs + list
lst = gimfont.read_lst(os.path.join(DST, 'rivaltalkfont_lst.txt'))
known = {c for c, _ in lst}
nxt = max(i for _, i in lst) + 1
atlases = {}
for ch in CYR:
    if ch in known:
        continue
    atlas, slot = divmod(nxt, 256)
    name = f'rivaltalkfont_{atlas:02d}.gim'
    if name not in atlases:
        atlases[name] = gimfont.Gim(os.path.join(DST, name))
    atlases[name].set_cell(slot, gimfont.render_glyph(ch))
    lst.append((ch, nxt))
    nxt += 1
for name, g in atlases.items():
    g.save(os.path.join(DST, name))
    g.to_png(os.path.join(ROOT, 'build', name + '.png'))
gimfont.write_lst(os.path.join(DST, 'rivaltalkfont_lst.txt'), lst)
print('glyphs:', nxt, 'atlases changed:', list(atlases))

# 2. scripts
jp = re.compile(r'[぀-ヿ一-鿿]')
lines_done = 0
for fn in os.listdir(DST):
    if not fn.startswith('talkTbl_'):
        continue
    p = os.path.join(DST, fn)
    text = open(p, 'rb').read().decode('cp932')
    out = []
    for line in text.split('\r\n'):
        m = re.fullmatch(r'"(.*)"', line)
        if m and jp.search(m.group(1)):
            line = '"' + (FULL if m.group(1).endswith('\\n') else PART) + '"'
            lines_done += 1
        out.append(line)
    open(p, 'wb').write('\r\n'.join(out).encode('cp932'))
print('lines replaced:', lines_done)

# 3. archive + iso
os.makedirs(os.path.dirname(ISO_OUT), exist_ok=True)
gz = os.path.join(ROOT, 'build', 'rivaldemo.bin.gz')
py = [sys.executable, '-I']
tools = os.path.dirname(os.path.abspath(__file__))
subprocess.check_call(py + [os.path.join(tools, 'xbb.py'), 'pack', DST, gz])
subprocess.check_call(py + [os.path.join(tools, 'isopatch.py'), 'replace', ISO_IN, ISO_OUT,
                            f'PSP_GAME/USRDIR/data/rivaldemo/rivaldemo.bin.gz={gz}'])
print('ISO:', ISO_OUT)
