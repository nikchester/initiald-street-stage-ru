"""Build a patched BOOT.BIN (relocatable PRX):

* the LOAD segment is extended past memsz with an extra region (code + data);
* the text renderer (0xb7bac) gets per-glyph advance widths: at 0xb7e10 the
  advance "cell width" is replaced by a call into WIDTH_FN, which looks up a
  width table for Shift-JIS lead bytes 0x84 (Cyrillic), 0x81 (punctuation),
  0x82 (full-width digits/Latin). 0 in the table = keep the cell width;
* strings that do not fit in place are moved to the extra region and every
  reference (R_MIPS_32 word, HI16/LO16 pair) is redirected.

Non-alloc sections (relocations, symbol tables, section headers) are moved
behind the grown segment; one R_MIPS_26 relocation is added for the new jal.
"""
import struct

import prx

# ---- tiny MIPS encoder ------------------------------------------------------
R = {'zero': 0, 'at': 1, 'v0': 2, 'v1': 3, 'a0': 4, 'a1': 5, 'a2': 6, 'a3': 7,
     't0': 8, 't1': 9, 't2': 10, 't3': 11, 't4': 12, 's0': 16, 's1': 17, 's2': 18, 's3': 19, 'ra': 31}


def _r(rs, rt, rd, sa, fn):
    return (R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | (sa << 6) | fn


def _i(op, rs, rt, imm):
    return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (imm & 0xffff)


def addu(rd, rs, rt): return _r(rs, rt, rd, 0, 0x21)
def lbu(rt, off, rs): return _i(0x24, rs, rt, off)
def lw(rt, off, rs): return _i(0x23, rs, rt, off)
def addiu(rt, rs, imm): return _i(0x09, rs, rt, imm)
def mult(rs, rt): return _r(rs, rt, 'zero', 0, 0x18)
def mflo(rd): return _r('zero', 'zero', rd, 0, 0x12)
def sra(rd, rt, sa): return _r('zero', rt, rd, sa, 0x03)
def jr(rs): return _r(rs, 'zero', 'zero', 0, 0x08)
NOP = 0


def beq(rs, rt, pc, target): return _i(0x04, rs, rt, (target - pc - 4) >> 2)
def bne(rs, rt, pc, target): return _i(0x05, rs, rt, (target - pc - 4) >> 2)
def bal(pc, target): return (1 << 26) | (0x11 << 16) | (((target - pc - 4) >> 2) & 0xffff)
def jal(target): return (3 << 26) | ((target >> 2) & 0x3ffffff)


HOOK_VA = 0xb7e10          # "lw v1,0x33c(s3)" in the advance code
HOOK_ORIG = (0x8e63033c, 0x8e620334)   # lw v1,0x33c(s3) ; lw v0,0x334(s3)
SPACE_VA = 0xb7cd4                     # lui v0,0x3f00 (0.5 * cell width for ' ')


def width_fn(base):
    """Code at vaddr base; width table (3 * 256 bytes) follows at base + 0x80."""
    tab = base + 0x80
    L = {}
    code = []

    def at(i):
        return base + i * 4
    # labels by instruction index
    L_L, L_CYR, L_NOT82, L_DONE = 6, 20, 16, 27
    code = [
        addu('t0', 's2', 's1'),                 # 0  t0 -> current char
        lbu('t1', 0, 't0'),                     # 1  lead byte
        lbu('t2', 1, 't0'),                     # 2  trail byte
        addu('t3', 'ra', 'zero'),               # 3  save ra
        bal(at(4), at(L_L)),                    # 4
        NOP,                                    # 5
        addiu('t0', 'ra', tab - at(L_L)),       # 6  L: t0 = table (pc-relative)
        addu('ra', 't3', 'zero'),               # 7  restore ra
        addiu('t4', 'zero', 0x84),              # 8
        beq('t1', 't4', at(9), at(L_CYR)),      # 9
        NOP,                                    # 10
        addiu('t4', 'zero', 0x82),              # 11
        bne('t1', 't4', at(12), at(L_NOT82)),   # 12
        NOP,                                    # 13
        beq('zero', 'zero', at(14), at(L_CYR)),  # 14
        addiu('t0', 't0', 512),                 # 15 (delay slot)
        addiu('t4', 'zero', 0x81),              # 16 NOT82
        bne('t1', 't4', at(17), at(L_DONE)),    # 17
        NOP,                                    # 18
        addiu('t0', 't0', 256),                 # 19
        addu('t0', 't0', 't2'),                 # 20 CYR
        lbu('t1', 0, 't0'),                     # 21
        beq('t1', 'zero', at(22), at(L_DONE)),  # 22
        NOP,                                    # 23
        mult('a0', 't1'),                       # 24
        mflo('a0'),                             # 25
        sra('a0', 'a0', 4),                     # 26
        jr('ra'),                               # 27 DONE
        lw('v0', 0x334, 's3'),                  # 28 (delay slot)
    ]
    blob = b''.join(struct.pack('<I', c) for c in code)
    return blob + b'\0' * (0x80 - len(blob))


def build(boot_bytes, strings, widths):
    """strings: list of (old_va, new_text) ; widths: {cp932 2-byte code: width}.
    Returns new BOOT.BIN bytes and a report."""
    p = prx.Prx(boot_bytes)
    refs = p.references()
    ext_va = (p.memsz + 0xf) & ~0xf
    ext = bytearray()

    # 1. width hook
    assert tuple(p.word(HOOK_VA + i * 4) for i in range(2)) == HOOK_ORIG, 'unexpected code at hook'
    fn_va = ext_va
    ext += width_fn(fn_va)
    table = bytearray(768)
    for code, w in widths.items():
        lead, trail = code >> 8, code & 0xff
        slot = {0x84: 0, 0x81: 256, 0x82: 512}.get(lead)
        if slot is not None:
            table[slot + trail] = max(1, min(255, w))
    ext += table
    p.set_word(HOOK_VA, jal(fn_va))
    p.set_word(HOOK_VA + 4, HOOK_ORIG[0])   # lw v1,0x33c(s3) in the delay slot
    new_rels = [(HOOK_VA, prx.R_26)]
    # ASCII space: 0.5 cell -> 0.375 cell (lui v0, 0x3f00 holds the float 0.5)
    assert p.word(SPACE_VA) == 0x3c023f00
    p.set_word(SPACE_VA, 0x3c023ec0)

    # 2. strings
    moved = inplace = 0
    for old_va, text in strings:
        data = text.encode('cp932')
        off = p.va2off(old_va)
        end = p.b.index(b'\0', off)
        nxt = end
        while p.b[nxt] == 0:
            nxt += 1
        cap = nxt - off - 1
        if len(data) <= cap:
            p.b[off:end] = b'\0' * (end - off)
            p.b[off:off + len(data)] = data
            inplace += 1
            continue
        if old_va not in refs:
            raise ValueError(f'no references to 0x{old_va:x}, cannot move: {text!r}')
        while len(ext) % 4:
            ext += b'\0'
        new_va = ext_va + len(ext)
        ext += data + b'\0'
        for ref in refs[old_va]:
            p.redirect(ref, new_va, old_va)
        moved += 1
    while len(ext) % 16:
        ext += b'\0'

    return _rebuild_elf(p, ext_va, bytes(ext), new_rels), {'inplace': inplace, 'moved': moved,
                                                          'ext_bytes': len(ext)}


def _rebuild_elf(p, ext_va, ext, new_rels):
    b = p.b
    seg_end_old = p.seg_off + p.filesz
    seg = bytes(b[p.seg_off:seg_end_old]) + b'\0' * (ext_va - p.filesz) + ext
    new_filesz = len(seg)
    head = bytearray(b[:p.seg_off])
    struct.pack_into('<II', head, p.phoff + 16, new_filesz, new_filesz)   # p_filesz, p_memsz
    out = head + seg
    # move every section that lives outside the segment
    secs = [list(s) for s in p.sections]
    for i, s in enumerate(secs):
        name = p.names[i]
        flags, off, size = s[2], s[4], s[5]
        if s[1] == 0 or s[1] == 8:   # NULL / NOBITS
            continue
        if flags & 2:               # SHF_ALLOC: inside the segment, unchanged
            continue
        data = bytes(b[off:off + size])
        if name == '.rel.text':
            data += b''.join(struct.pack('<II', va, typ) for va, typ in new_rels)
        while len(out) % 4:
            out += b'\0'
        s[4] = len(out)
        s[5] = len(data)
        out += data
    while len(out) % 4:
        out += b'\0'
    shoff = len(out)
    for s in secs:
        out += struct.pack('<10I', *s)
    struct.pack_into('<I', out, 0x20, shoff)
    return bytes(out)
