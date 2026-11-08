"""Relocatable PSP module (BOOT.BIN, ELF type 0xFFA0) helpers.

One LOAD segment at vaddr 0 (file offset SEG_OFF). Relocation sections of type
0x700000A0 hold Elf32_Rel {r_offset, r_info}; r_info: type = bits 0-7,
offset base segment = bits 8-15, address base segment = bits 16-23.
Types: 2 = R_MIPS_32, 4 = R_MIPS_26, 5 = R_MIPS_HI16, 6 = R_MIPS_LO16.

Strings are found through relocations: R_MIPS_32 words and HI16/LO16 pairs
whose combined value is the string address.
"""
import struct

R_32, R_26, R_HI16, R_LO16 = 2, 4, 5, 6
SHT_PSPREL = 0x700000A0


class Prx:
    def __init__(self, data):
        self.b = bytearray(data)
        b = self.b
        assert b[:4] == b'\x7fELF'
        self.phoff = struct.unpack_from('<I', b, 0x1c)[0]
        self.shoff = struct.unpack_from('<I', b, 0x20)[0]
        self.shnum = struct.unpack_from('<H', b, 0x30)[0]
        self.shstrndx = struct.unpack_from('<H', b, 0x32)[0]
        (_, self.seg_off, self.seg_va, _, self.filesz, self.memsz, _, _) = struct.unpack_from('<8I', b, self.phoff)
        self.sections = [list(struct.unpack_from('<10I', b, self.shoff + i * 40)) for i in range(self.shnum)]
        so = self.sections[self.shstrndx][4]
        self.names = [b[so + s[0]:b.index(b'\0', so + s[0])].decode() for s in self.sections]
        self.rels = []  # (file offset of rel entry, r_offset, type)
        for s in self.sections:
            if s[1] == SHT_PSPREL:
                for k in range(s[5] // 8):
                    off, info = struct.unpack_from('<II', b, s[4] + k * 8)
                    self.rels.append((s[4] + k * 8, off, info & 0xff, (info >> 8) & 0xff, (info >> 16) & 0xff))

    def va2off(self, va):
        return va - self.seg_va + self.seg_off

    def off2va(self, off):
        return off - self.seg_off + self.seg_va

    def word(self, va):
        return struct.unpack_from('<I', self.b, self.va2off(va))[0]

    def set_word(self, va, v):
        struct.pack_into('<I', self.b, self.va2off(va), v & 0xffffffff)

    def references(self):
        """Return {target vaddr: [ref, ...]}; ref = ('w32', va) or ('hilo', hi_va, lo_va)."""
        refs = {}
        pending_hi = []
        for _, r_off, typ, _, _ in self.rels:
            if typ == R_32:
                refs.setdefault(self.word(r_off), []).append(('w32', r_off))
            elif typ == R_HI16:
                pending_hi.append(r_off)
            elif typ == R_LO16:
                lo = self.word(r_off) & 0xffff
                lo_s = lo - 0x10000 if lo & 0x8000 else lo
                if pending_hi:
                    for hi_va in pending_hi:
                        hi = self.word(hi_va) & 0xffff
                        refs.setdefault(((hi << 16) + lo_s) & 0xffffffff, []).append(('hilo', hi_va, r_off))
                    self._last_hi = pending_hi
                    pending_hi = []
                elif getattr(self, '_last_hi', None):
                    # several LO16 may follow one HI16
                    for hi_va in self._last_hi:
                        hi = self.word(hi_va) & 0xffff
                        refs.setdefault(((hi << 16) + lo_s) & 0xffffffff, []).append(('hilo', hi_va, r_off))
        return refs

    def redirect(self, ref, new_va, old_va):
        """Point one reference at new_va (keeping any offset it had from old_va)."""
        if ref[0] == 'w32':
            self.set_word(ref[1], self.word(ref[1]) - old_va + new_va)
            return
        _, hi_va, lo_va = ref
        hi = self.word(hi_va) & 0xffff
        lo = self.word(lo_va) & 0xffff
        lo_s = lo - 0x10000 if lo & 0x8000 else lo
        target = ((hi << 16) + lo_s) - old_va + new_va
        nlo = target & 0xffff
        nhi = ((target - (nlo - 0x10000 if nlo & 0x8000 else nlo)) >> 16) & 0xffff
        self.set_word(hi_va, (self.word(hi_va) & 0xffff0000) | nhi)
        self.set_word(lo_va, (self.word(lo_va) & 0xffff0000) | nlo)
