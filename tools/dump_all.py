"""Dump every GIM of the menu archives to work/png/all, grouped by content.

Output: work/png/all/<hash>.png (one file per unique image) and
work/png/all/index.json: {hash: {"size": [w, h], "fmt": f, "where": [[file, gim path], ...]}}
"""
import gzip
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gim  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'extracted', 'PSP_GAME', 'USRDIR', 'data')
OUT = os.path.join(ROOT, 'work', 'png', 'all')
SKIP = ('course', 'car', 'rivaldemo', 'cam_data', 'effect', 'sound', 'movie', 'test')


def main():
    os.makedirs(OUT, exist_ok=True)
    index = {}
    for root, _, files in os.walk(DATA):
        rel_root = os.path.relpath(root, DATA).replace(os.sep, '/')
        if rel_root.split('/')[0] in SKIP:
            continue
        for f in files:
            if not f.endswith(('.bin', '.gz', '.ana', '.gim')):
                continue
            rel = f'{rel_root}/{f}'.lstrip('./')
            d = open(os.path.join(root, f), 'rb').read()
            if d[:2] == b'\x1f\x8b':
                d = gzip.decompress(d)
            for name, g in gim.find_gims(d):
                key = hashlib.md5(g).hexdigest()[:12]
                if key not in index:
                    try:
                        im, info = gim.gim_to_image(g)
                    except Exception:  # noqa: BLE001
                        continue
                    im.save(os.path.join(OUT, key + '.png'))
                    index[key] = {'size': [info['w'], info['h']], 'fmt': info['fmt'], 'where': []}
                index[key]['where'].append([rel, name])
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w'), indent=0)
    print(len(index), 'unique images')


if __name__ == '__main__':
    main()
