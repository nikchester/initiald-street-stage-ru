"""Build the Russian ISO from the original image.

  python tools/build.py [--out build/InitialD_RU.iso]

Steps:
  1. generate Russian menu graphics (IMAGE_PARTS generators);
  2. BOOT.BIN: translations from text/boot_ru_*.json, proportional font hook;
     the result also replaces the encrypted EBOOT.BIN;
  3. every archive with a text font gets Russian glyphs; archives with menu
     graphics get the new images;
  4. changed files go into a copy of the ISO (lba.dat is updated).
"""
import argparse
import gzip
import os
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import boot_build  # noqa: E402
import fonts  # noqa: E402
import gim  # noqa: E402
import imgtr  # noqa: E402
import rutext  # noqa: E402
import talk  # noqa: E402
import texts  # noqa: E402
import xbb  # noqa: E402

ISO_IN = os.path.join(ROOT, 'Initital_D_Street_Stage_JAP_PSP-DMU.iso')
EXT = os.path.join(ROOT, 'extracted', 'PSP_GAME')
DATA = os.path.join(EXT, 'USRDIR', 'data')
OUT = os.path.join(ROOT, 'build', 'files')

# archive (relative to data/) -> (folder with Russian PNGs, generator script)
IMAGE_PARTS = {
    'select/sel_gamemode.bin.gz': ('work/ru/sel_gamemode', 'menu_gamemode.py'),
}
# archive -> function(items) -> (pairs [(jp, game text)], info); translates text files in place
TEXT_PARTS = {}
TEXT_PARTS.update(texts.PARTS)
# rival dialogues stay Japanese (user decision): the archive is left untouched
SKIP_ARCHIVES = {'rivaldemo/rivaldemo.bin.gz'}
SKIP_DIRS = ('course', os.sep + 'car' + os.sep)
JP = re.compile(r'[぀-ヿ一-鿿]')


def archives():
    for root, _, files in os.walk(DATA):
        if any(s in root + os.sep for s in SKIP_DIRS):
            continue
        for f in files:
            if f.endswith(('.bin', '.bin.gz')):
                yield os.path.relpath(os.path.join(root, f), DATA).replace(os.sep, '/')


def load_items(path):
    d, gz = xbb.load(path)
    if d[:4] != b'XBB\x01':
        return None, gz
    return [(e['name'], e['hash'], d[e['off']:e['off'] + e['size']]) for e in xbb.parse(d)], gz


def archive_texts(items):
    """Untranslated text pieces (lines) of the text files in one archive."""
    out = []
    if True:
        for name, _, data in items or []:
            if name.endswith('.txt') and not name.endswith('_lst.txt') and not name.endswith('tbl.txt'):
                out.extend(re.split(r'[\r\n"]+', data.decode('cp932', 'replace')))
    return [t for t in out if JP.search(t)]


def drawable(text, have):
    """True if a font with characters `have` can draw every character of text."""
    cs = {c for c in text if c not in ' \n\r' and ord(c) > 0x7f}
    return bool(cs) and cs <= have


# fonts that also draw player-typed names: only these texts get Russian glyphs,
# and every kana stays
NAME_FONTS = {
    'PSP_option_player_18font_lst.txt': {'新規作成', 'データがありません', 'データがこわれています'},
}
KANA = re.compile(r'[぀-ヿ]')


def font_needs(lst_data, pairs, lst_name=''):
    """Characters of Russian texts whose Japanese originals this font can draw."""
    have = {c for c, _ in fonts.fontset.parse_lst(lst_data)}
    only = NAME_FONTS.get(lst_name)
    need = ''
    for jp, ru in pairs:
        if (jp in only) if only else drawable(jp, have):
            need += ru
    return ''.join(dict.fromkeys(c for c in need if c not in ' \n'))


def font_keeps(lst_data, texts):
    """Japanese characters of a font that some untranslated text may need:
    a text can use this font only if the font has all of its characters."""
    have = {c for c, _ in fonts.fontset.parse_lst(lst_data)}
    keep = set()
    for t in texts:
        js = set(JP.findall(t))
        if js and js <= have:
            keep |= js
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'InitialD_RU.iso'))
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    for rel, (png_dir, gen) in IMAGE_PARTS.items():
        subprocess.check_call([sys.executable, '-I', os.path.join(TOOLS, gen)])

    boot = open(os.path.join(EXT, 'SYSDIR', 'BOOT.BIN'), 'rb').read()
    new_boot, rep, warnings, pairs_tr, remaining = boot_build.build(boot)
    print('BOOT.BIN:', rep)
    for w in warnings:
        print('  wide line', w)
    boot_path = os.path.join(OUT, 'BOOT.BIN')
    open(boot_path, 'wb').write(new_boot)
    pairs = [f'PSP_GAME/SYSDIR/BOOT.BIN={boot_path}', f'PSP_GAME/SYSDIR/EBOOT.BIN={boot_path}']

    rels = list(archives())
    cache = {}
    specs = imgtr.load_specs()
    icache = {}
    # loose .ana / .gim files
    for root, _, files in os.walk(DATA):
        for f in files:
            if not f.endswith(('.ana', '.gim')):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, DATA).replace(os.sep, '/')
            raw = open(path, 'rb').read()
            done_img = []
            new = imgtr.transform(raw, specs, done_img, icache)
            if new != raw:
                dst = os.path.join(OUT, rel.replace('/', '__'))
                open(dst, 'wb').write(new)
                pairs.append(f'PSP_GAME/USRDIR/data/{rel}={dst}')
                print(f'{rel}: {len(done_img)} images redrawn')
    for rel in rels:
        if rel in SKIP_ARCHIVES:
            continue
        src = os.path.join(DATA, *rel.split('/'))
        items, gz = load_items(src)
        if items is None:
            continue
        done_img = []
        items = [(n, h, imgtr.transform(d, specs, done_img, icache)) for n, h, d in items]
        names = {n for n, _, _ in items}
        font_lsts = [n for n in names if n in fonts.FONTS]
        if not font_lsts and rel not in IMAGE_PARTS and rel not in TEXT_PARTS and not done_img:
            continue
        if done_img:
            print(f'{rel}: {len(done_img)} images redrawn')
        local_pairs = []
        if rel in TEXT_PARTS:
            local_pairs, info = TEXT_PARTS[rel](items)
            print(f'{rel}: text {len(local_pairs)} translated, {info} missing')
        if rel in IMAGE_PARTS:
            png_dir = os.path.join(ROOT, IMAGE_PARTS[rel][0])
            done = []
            items = [(n, h, gim.inject_bytes(d, png_dir, f'{n}/', done)) for n, h, d in items]
            print(f'{rel}: {len(done)} images')
        for lst in font_lsts:
            lst_data = next(d for n, _, d in items if n == lst)
            needed = font_needs(lst_data, pairs_tr + local_pairs, lst)
            if not needed:
                continue
            keep = font_keeps(lst_data, remaining + archive_texts(items))
            if lst in NAME_FONTS:
                keep |= {c for c, _ in fonts.fontset.parse_lst(lst_data) if KANA.match(c)}
            info = fonts.build_font(items, lst, needed, keep, cache)
            print(f'{rel}: {lst} {info}')
        dst = os.path.join(OUT, rel.replace('/', '__'))
        xbb.save(dst, xbb.build(items), gz, os.path.basename(rel))
        pairs.append(f'PSP_GAME/USRDIR/data/{rel}={dst}')

    subprocess.check_call([sys.executable, '-I', os.path.join(TOOLS, 'isopatch.py'), 'replace',
                           ISO_IN, args.out] + pairs)
    print('ISO:', args.out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
