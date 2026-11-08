"""Replace files inside the Initial D Street Stage ISO.

The game does not use ISO9660 to find its data. It reads PSP_GAME/USRDIR/lba.dat,
an XBB-style index: {u32 byte_offset, u32 size, u32 0, u32 path_hash} per file.
So when a file changes, both the ISO9660 directory record and the lba.dat entry
must be updated.

A replaced file stays in place if it fits before the next file; otherwise it is
appended at the end of the image (aligned to 0x8000, like the original layout).

  python isopatch.py check   <iso>
  python isopatch.py replace <src_iso> <dst_iso> <iso/path>=<local file> [...]
"""
import os
import shutil
import struct
import sys

SECTOR = 2048
FILE_ALIGN = 0x8000
LBA_DAT = 'PSP_GAME/USRDIR/lba.dat'


class Iso:
    def __init__(self, path, mode='rb'):
        self.f = open(path, mode)
        self.files = {}  # path -> dict(rec=abs offset of dir record, lba, size)
        pvd = self.read(16 * SECTOR, SECTOR)
        assert pvd[1:6] == b'CD001'
        self.volume_blocks = struct.unpack_from('<I', pvd, 80)[0]
        root = pvd[156:156 + 34]
        self._walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')

    def read(self, off, n):
        self.f.seek(off)
        return self.f.read(n)

    def write(self, off, data):
        self.f.seek(off)
        self.f.write(data)

    def _walk(self, lba, size, prefix):
        data = self.read(lba * SECTOR, size)
        pos = 0
        while pos < size:
            ln = data[pos]
            if ln == 0:  # records never cross sectors
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            rec = data[pos:pos + ln]
            elba, esize = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
            flags, nlen = rec[25], rec[32]
            name = rec[33:33 + nlen]
            if name not in (b'\0', b'\1'):
                name = name.decode('ascii').split(';')[0]
                path = prefix + name
                if flags & 2:
                    self._walk(elba, esize, path + '/')
                else:
                    self.files[path] = {'rec': lba * SECTOR + pos, 'lba': elba, 'size': esize}
            pos += ln

    def set_record(self, path, lba, size):
        e = self.files[path]
        self.write(e['rec'] + 2, struct.pack('<I', lba) + struct.pack('>I', lba))
        self.write(e['rec'] + 10, struct.pack('<I', size) + struct.pack('>I', size))
        e['lba'], e['size'] = lba, size

    def end(self):
        self.f.seek(0, 2)
        return self.f.tell()

    def lba_index(self):
        e = self.files[LBA_DAT]
        d = self.read(e['lba'] * SECTOR, e['size'])
        n = struct.unpack_from('<I', d, 4)[0]
        by_off = {}
        for i in range(n):
            off, size, _, h = struct.unpack_from('<IIII', d, 0x20 + i * 16)
            by_off.setdefault(off, []).append(i)
        return d, by_off


def check(iso_path):
    iso = Iso(iso_path)
    d, by_off = iso.lba_index()
    n = struct.unpack_from('<I', d, 4)[0]
    usr = [p for p in iso.files if p.startswith('PSP_GAME/USRDIR/')]
    hit = sum(1 for p in usr if iso.files[p]['lba'] * SECTOR in by_off)
    print(f'lba.dat entries: {n}; USRDIR files: {len(usr)}; matched by offset: {hit}')
    for p in usr:
        if iso.files[p]['lba'] * SECTOR not in by_off:
            print('  not indexed:', p)


def replace(src, dst, pairs):
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    iso = Iso(dst, 'r+b')
    lba_raw, by_off = iso.lba_index()
    lba = bytearray(lba_raw)
    starts = sorted(f['lba'] * SECTOR for f in iso.files.values())
    for iso_path, local in pairs:
        data = open(local, 'rb').read()
        e = iso.files[iso_path]
        old = e['lba'] * SECTOR
        idx = by_off.get(old, [])
        nxt = next((s for s in starts if s > old), iso.end())
        if old + len(data) <= nxt:
            new = old
        else:
            new = (iso.end() + FILE_ALIGN - 1) // FILE_ALIGN * FILE_ALIGN
        pad = (-len(data)) % SECTOR
        iso.write(new, data + b'\0' * pad)
        iso.set_record(iso_path, new // SECTOR, len(data))
        for i in idx:
            struct.pack_into('<II', lba, 0x20 + i * 16, new, len(data))
        where = 'in place' if new == old else f'moved to 0x{new:x}'
        print(f'{iso_path}: {len(data)} bytes, {where}, lba.dat entries: {len(idx)}')
        if not idx and iso_path.startswith('PSP_GAME/USRDIR/'):
            print('  WARNING: file not found in lba.dat')
    e = iso.files[LBA_DAT]
    iso.write(e['lba'] * SECTOR, bytes(lba))
    blocks = (iso.end() + SECTOR - 1) // SECTOR
    if blocks * SECTOR != iso.end():
        iso.write(iso.end(), b'\0' * (blocks * SECTOR - iso.end()))
    iso.write(16 * SECTOR + 80, struct.pack('<I', blocks) + struct.pack('>I', blocks))
    iso.f.close()


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'check':
        check(sys.argv[2])
    elif cmd == 'replace':
        replace(sys.argv[2], sys.argv[3], [a.split('=', 1) for a in sys.argv[4:]])
