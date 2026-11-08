"""Build the Russian ISO from the original image and work/ru/*.

  python tools/build.py

Each entry of PARTS: (ISO path, folder with Russian PNGs, generator script or None).
"""
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import gim  # noqa: E402

ISO_IN = os.path.join(ROOT, 'Initital_D_Street_Stage_JAP_PSP-DMU.iso')
ISO_OUT = os.path.join(ROOT, 'build', 'InitialD_RU.iso')
EXTRACTED = os.path.join(ROOT, 'extracted')
OUT = os.path.join(ROOT, 'build', 'files')

PARTS = [
    ('PSP_GAME/USRDIR/data/select/sel_gamemode.bin.gz', 'work/ru/sel_gamemode', 'menu_gamemode.py'),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    pairs = []
    for iso_path, png_dir, gen in PARTS:
        if gen:
            subprocess.check_call([sys.executable, '-I', os.path.join(TOOLS, gen)])
        src = os.path.join(EXTRACTED, *iso_path.split('/'))
        dst = os.path.join(OUT, os.path.basename(iso_path))
        gim.inject(src, os.path.join(ROOT, png_dir), dst)
        pairs.append(f'{iso_path}={dst}')
    subprocess.check_call([sys.executable, '-I', os.path.join(TOOLS, 'isopatch.py'), 'replace',
                           ISO_IN, ISO_OUT] + pairs)
    print('ISO:', ISO_OUT)


if __name__ == '__main__':
    main()
