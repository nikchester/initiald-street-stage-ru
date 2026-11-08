"""Extract translatable strings from BOOT.BIN -> work/text/boot_jp.json

A string qualifies when it starts after a zero byte, decodes as cp932,
contains Japanese characters and is referenced through a relocation.
Output: [{"id": "<vaddr hex>", "jp": "..."}], in address order.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import prx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP = re.compile(r'[぀-ヿ一-鿿！-～]')
PAT = re.compile(rb'(?:[\x81-\x84\x88-\x9f\xe0-\xea][\x40-\x7e\x80-\xfc]|[\x0a\x20-\x7e])+')


def extract(boot):
    p = prx.Prx(boot)
    refs = p.references()
    out = []
    lo, hi = p.va2off(0x1b9894), p.va2off(0x2537f0)   # .data
    for m in PAT.finditer(p.b, lo, hi):
        s = m.start()
        if p.b[s - 1] != 0 or p.b[m.end()] != 0:
            continue
        va = p.off2va(s)
        if va not in refs:
            continue
        try:
            t = m.group().decode('cp932')
        except UnicodeDecodeError:
            continue
        if not JP.search(t):
            continue
        out.append({'id': f'{va:06x}', 'jp': t})
    return out


if __name__ == '__main__':
    boot = open(os.path.join(ROOT, 'extracted', 'PSP_GAME', 'SYSDIR', 'BOOT.BIN'), 'rb').read()
    items = extract(boot)
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    path = os.path.join(ROOT, 'work', 'text', 'boot_jp.json')
    json.dump(items, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    uniq = {i['jp'] for i in items}
    print(f'{len(items)} strings, {len(uniq)} unique, {sum(len(u) for u in uniq)} chars -> {path}')
