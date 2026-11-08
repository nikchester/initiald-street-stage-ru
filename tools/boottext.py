"""Edit Shift-JIS strings in BOOT.BIN (unencrypted ELF of the game).

Strings are zero-terminated, start on a 4-byte boundary, '\\n' = 0x0a.
In-place replacement may use the original bytes plus the zero padding
up to the next non-zero byte (keeping one terminating zero).
"""


def string_at(boot, off):
    end = boot.index(b'\0', off)
    return boot[off:end].decode('cp932')


def capacity(boot, off):
    """Bytes available for text at off (without the terminating zero)."""
    end = boot.index(b'\0', off)
    nxt = end
    while nxt < len(boot) and boot[nxt] == 0:
        nxt += 1
    # the next string starts at nxt; keep at least one zero before it
    return nxt - off - 1


def find_string(boot, text):
    """Offsets of strings that start with text."""
    k = text.encode('cp932')
    out = []
    i = boot.find(k)
    while i >= 0:
        if i == 0 or boot[i - 1] == 0:
            out.append(i)
        i = boot.find(k, i + 1)
    return out


def replace_inplace(boot, off, new):
    """boot: bytearray. Raises ValueError if new text does not fit."""
    data = new.encode('cp932')
    cap = capacity(boot, off)
    if len(data) > cap:
        raise ValueError(f'0x{off:x}: {len(data)} bytes > capacity {cap}: {new!r}')
    end = boot.index(b'\0', off)
    boot[off:end] = b'\0' * (end - off)
    boot[off:off + len(data)] = data
    return len(data), cap
