"""Test: Russian text in BOOT.BIN with the proportional renderer.

Input: build/InitialD_RU.iso (run build.py first).
Output: build/InitialD_RU_boottest.iso. The patched BOOT.BIN is also put in
place of the encrypted EBOOT.BIN.
"""
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import boottext  # noqa: E402
import bootpatch  # noqa: E402
import fontset  # noqa: E402
import prx  # noqa: E402
import rutext  # noqa: E402

EXT = os.path.join(ROOT, 'extracted', 'PSP_GAME')
OUT = os.path.join(ROOT, 'build', 'files')
ISO_IN = os.path.join(ROOT, 'build', 'InitialD_RU.iso')
ISO_OUT = os.path.join(ROOT, 'build', 'InitialD_RU_boottest.iso')

TEXTS = [
    ('システムデータがありません。\nメモリースティックФにシステムデータを\n新しく作成しますか？',
     'Системных данных нет.\nСоздать новые системные данные\nна Memory Stick?'),
    ('セーブしないでゲームを開始します。\nよろしいですか？\nオプションで',
     'Игра начнётся без сохранения. Продолжить?\n'
     'Пока вы не создадите сохранение в настройках,\nавтосохранение работать не будет.'),
]
MS_ERROR_ARCHIVES = ['save/save_data.bin.gz', 'memscene/memscene.bin.gz', 'homepage/hp_data_00.bin.gz']


def main():
    os.makedirs(OUT, exist_ok=True)
    boot = open(os.path.join(EXT, 'SYSDIR', 'BOOT.BIN'), 'rb').read()
    p = prx.Prx(boot)
    strings, chars = [], ''
    for jp, ru in TEXTS:
        offs = boottext.find_string(p.b, jp)
        assert len(offs) == 1, (jp, offs)
        game = rutext.to_game(ru)
        strings.append((p.off2va(offs[0]), game))
        chars += game
    new_boot, rep = bootpatch.build(boot, strings, rutext.width_table())
    print('BOOT.BIN:', rep)
    boot_path = os.path.join(OUT, 'BOOT.BIN')
    open(boot_path, 'wb').write(new_boot)

    uniq = ''.join(dict.fromkeys(c for c in chars if c not in ' \n'))
    fontset.add_chars.__defaults__ = (lambda ch: rutext.glyph(ch)[0],)
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
