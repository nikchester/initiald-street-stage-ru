"""Test: Russian text in BOOT.BIN (save dialogs) + Cyrillic in ms_error font.

Input: build/InitialD_RU.iso (run build.py first).
Output: build/InitialD_RU_boottest.iso. BOOT.BIN is patched and also put in
place of the encrypted EBOOT.BIN.
"""
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import boottext  # noqa: E402
import fontset  # noqa: E402
import gimfont  # noqa: E402

EXT = os.path.join(ROOT, 'extracted', 'PSP_GAME')
OUT = os.path.join(ROOT, 'build', 'files')
ISO_IN = os.path.join(ROOT, 'build', 'InitialD_RU.iso')
ISO_OUT = os.path.join(ROOT, 'build', 'InitialD_RU_boottest.iso')

TEXTS = [
    ('システムデータがありません。\nメモリースティックФにシステムデータを\n新しく作成しますか？',
     'Нет системных данных．\nСоздать их？'),
    ('セーブしないでゲームを開始します。\nよろしいですか？\nオプションで',
     'Играть без сохранения？\nАвтосохранение будет\nотключено．'),
]
MS_ERROR_ARCHIVES = ['save/save_data.bin.gz', 'memscene/memscene.bin.gz', 'homepage/hp_data_00.bin.gz']


def glyph(ch):
    if ch == '．':
        return gimfont.render_glyph('.', r'C:\Windows\Fonts\YuGothM.ttc', 15)
    return gimfont.render_glyph(ch, r'C:\Windows\Fonts\YuGothM.ttc', 15)


def main():
    os.makedirs(OUT, exist_ok=True)
    boot = bytearray(open(os.path.join(EXT, 'SYSDIR', 'BOOT.BIN'), 'rb').read())
    chars = ''
    for jp, ru in TEXTS:
        offs = boottext.find_string(boot, jp)
        assert len(offs) == 1, (jp, offs)
        used, cap = boottext.replace_inplace(boot, offs[0], ru)
        print(f'0x{offs[0]:x}: {used}/{cap} bytes')
        chars += ru
    boot_path = os.path.join(OUT, 'BOOT.BIN')
    open(boot_path, 'wb').write(boot)

    fontset.add_chars.__defaults__ = (glyph,)
    uniq = ''.join(dict.fromkeys(chars))
    pairs = [f'PSP_GAME/SYSDIR/BOOT.BIN={boot_path}', f'PSP_GAME/SYSDIR/EBOOT.BIN={boot_path}']
    for a in MS_ERROR_ARCHIVES:
        dst = os.path.join(OUT, os.path.basename(a))
        fontset.patch_archive(os.path.join(EXT, 'USRDIR', 'data', *a.split('/')), dst,
                              [('ms_error_lst.txt', 'ms_error', uniq)])
        pairs.append(f'PSP_GAME/USRDIR/data/{a}={dst}')
    subprocess.check_call([sys.executable, '-I', os.path.join(TOOLS, 'isopatch.py'), 'replace',
                           ISO_IN, ISO_OUT] + pairs)
    print('ISO:', ISO_OUT)


if __name__ == '__main__':
    main()
