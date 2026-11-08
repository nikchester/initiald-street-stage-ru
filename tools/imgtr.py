"""Generic Russian redraw of menu graphics, driven by text/images_ru_*.json.

Spec per image hash (md5 of the original GIM bytes, 12 hex):
  {"header": "TEXT"}                 title bar (red/blue gradient, white text)
  {"footer": ["label", ...]}         button hint bar (orange labels after icons)
  {"header": ..., "footer": [...]}   512x64: header on top, footer below
  {"sprite": "TEXT", ...}            text on a transparent background (see render_sprite)
"""
import glob
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import gim  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = r'C:\Windows\Fonts'
F_TITLE = FONTS + r'\seguibli.ttf'
F_LABEL = FONTS + r'\ARIALNB.TTF'
F_BOLD = FONTS + r'\segoeuib.ttf'
ORANGE = (252, 163, 7, 255)


def load_specs():
    specs = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'text', 'images_ru_*.json'))):
        for k, v in json.load(open(p, encoding='utf-8')).items():
            if not k.startswith('_'):
                specs[k] = v
    return specs


def ghash(g):
    return hashlib.md5(g).hexdigest()[:12]


def luma(p):
    return (p[0] * 3 + p[1] * 6 + p[2]) // 10


def fit(path, text, max_w, max_h, start=40, stroke=0):
    dr = ImageDraw.Draw(Image.new('L', (1, 1)))
    for size in range(start, 6, -1):
        f = ImageFont.truetype(path, size)
        l, t, r, b = dr.textbbox((0, 0), text, font=f, stroke_width=stroke)
        if r - l <= max_w and b - t <= max_h:
            return f
    return ImageFont.truetype(path, 7)


# ---------------------------------------------------------------- header
def draw_header(im, text, y0, y1):
    """Bar rows y0..y1 (exclusive). Background = vertical gradient."""
    W = im.width
    px = im.load()
    opaque = [x for x in range(W) if px[x, (y0 + y1) // 2][3] > 200]
    if not opaque:
        return
    x_end = opaque[-1] + 1
    # rows of the bright bottom line stay untouched
    rows = [y for y in range(y0, y1) if luma(px[3, y]) < 200 or px[3, y][0] > 200 and px[3, y][2] < 100]
    rows = [y for y in rows if not (luma(px[3, y]) > 200)]
    if not rows:
        return
    ty0, ty1 = rows[0], rows[-1] + 1
    for y in range(ty0, ty1):
        c = px[3, y]
        for x in range(0, x_end):
            px[x, y] = c
    h = ty1 - ty0
    f = fit(F_TITLE, text, x_end - 30, int(h * 0.62))
    dr = ImageDraw.Draw(im)
    l, t, r, b = dr.textbbox((0, 0), text, font=f)
    x = (x_end - (r - l)) / 2 - l
    y = ty0 + (h - (b - t)) / 2 - t
    base = px[3, (ty0 + ty1) // 2]
    shadow = tuple(int(v * 0.35) for v in base[:3]) + (255,)
    dr.text((x + 2, y + 2), text, font=f, fill=shadow)
    dr.text((x, y), text, font=f, fill=(255, 255, 255, 255))


# ---------------------------------------------------------------- footer
def is_orange(p):
    return p[3] > 128 and p[0] > 140 and 60 < p[1] < 210 and p[2] < 90 and p[0] - p[2] > 110


def draw_footer(im, labels, y0, y1):
    W = im.width
    px = im.load()
    cols_or = [x for x in range(W) if any(is_orange(px[x, y]) for y in range(y0, y1))]
    if not cols_or:
        return False
    clusters = []
    s = p = cols_or[0]
    for x in cols_or[1:]:
        if x > p + 7:
            clusters.append((s, p))
            s = x
        p = x
    clusters.append((s, p))
    if len(clusters) != len(labels):
        print(f'    footer: {len(clusters)} label areas, {len(labels)} labels', file=sys.stderr)
        return False
    rows_or = [y for y in range(y0, y1) if any(is_orange(px[x, y]) for x in cols_or)]
    oy0, oy1 = rows_or[0], rows_or[-1]
    # icons / separators / text between the label rows (the bar border is excluded)
    busy = [x for x in range(W) if any(px[x, y][3] > 128 and luma(px[x, y]) > 95 for y in range(oy0, oy1 + 1))]
    orange_set = {x for a, b in clusters for x in range(a - 3, b + 5)}   # incl. anti-aliased edges
    first_busy = min(busy) if busy else W
    clean0, clean1 = 2, max(6, first_busy - 3)
    ey0, ey1 = max(y0, oy0 - 2), min(y1, oy1 + 3)
    opaque = [x for x in range(W) if px[x, (y0 + y1) // 2][3] > 200]
    x_end = opaque[-1] + 1 if opaque else W
    # erase every label area with the carbon pattern copied from the clean zone
    for a, b in clusters:
        x = a - 1
        while x <= b + 2:
            width = min(b + 3 - x, clean1 - clean0)
            dx = ((x - clean0) // 4) * 4
            src = x - dx
            if src < clean0:
                src += 4
                dx -= 4
            patch = im.crop((src, ey0, src + width, ey1))
            im.paste(patch, (x, ey0))
            x += width
    dr = ImageDraw.Draw(im)
    for (a, b), label in zip(clusters, labels):
        nxt = [x for x in busy if x > b + 4 and x not in orange_set]
        limit = (min(nxt) - 3) if nxt else x_end - 2
        prev = [x for x in busy if x < a - 1 and x not in orange_set]
        start = (max(prev) + 3) if prev else a
        start = min(start, a)
        avail = max(b - a + 1, limit - start)
        f = fit(F_LABEL, label, avail, oy1 - oy0 + 3, start=12)
        l, t, r, bb = dr.textbbox((0, 0), label, font=f)
        w = r - l
        x = a if a + w <= limit else max(start, limit - w)
        y = (oy0 + oy1) / 2 - (bb - t) / 2 - t
        dr.text((x - l, y), label, font=f, fill=ORANGE)
    return True


# ---------------------------------------------------------------- sprites
def render_sprite(im, spec):
    """Text on transparent background, placed in the original ink box.
    spec: sprite text, optional fill [r,g,b], outline [r,g,b], font ('title'|'bold'|'label'), align."""
    a = im.getchannel('A')
    box = a.getbbox()
    if not box:
        return
    x0, y0, x1, y1 = box
    fill = tuple(spec.get('fill', [255, 255, 255])) + (255,)
    outline = spec.get('outline')
    path = {'title': F_TITLE, 'bold': F_BOLD, 'label': F_LABEL}[spec.get('font', 'bold')]
    stroke = spec.get('stroke', 2 if outline else 0)
    max_w = spec.get('max_w', max(x1 - x0, int(im.width * 0.9) if spec.get('wide') else x1 - x0))
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    lines = spec['sprite'].split('\n')
    lh = (y1 - y0) / len(lines)
    dr = ImageDraw.Draw(out)
    for i, line in enumerate(lines):
        f = fit(path, line, max_w, lh - 1, start=60, stroke=stroke)
        l, t, r, b = dr.textbbox((0, 0), line, font=f, stroke_width=stroke)
        align = spec.get('align', 'center')
        if align == 'left':
            x = x0 - l
        elif align == 'right':
            x = x1 - (r - l) - l
        else:
            x = (x0 + x1) / 2 - (r - l) / 2 - l
        x = max(-l, min(x, im.width - (r - l) - l))
        y = y0 + i * lh + (lh - (b - t)) / 2 - t
        kw = {'stroke_width': stroke, 'stroke_fill': tuple(outline) + (255,)} if outline else {}
        dr.text((x, y), line, font=f, fill=fill, **kw)
    im.paste(out, (0, 0))
    im.putalpha(out.getchannel('A'))


# ---------------------------------------------------------------- plates
def draw_plate(im, text, spec):
    """Brushed-metal button with bolts at both ends and dark italic text."""
    px = im.load()
    W, H = im.size
    rows = [y for y in range(H) if px[W // 2, y][3] > 200]
    if not rows:
        return
    y0, y1 = rows[0], rows[-1] + 1
    opaque = [x for x in range(W) if px[x, (y0 + y1) // 2][3] > 200]
    xa, xb = opaque[0], opaque[-1] + 1
    src = xa + spec.get('clean_x', 16)
    margin = spec.get('margin', 14)
    for y in range(y0 + 2, y1 - 2):
        c = px[src, y]
        for x in range(xa + margin, xb - margin):
            px[x, y] = c
    f = fit(F_TITLE, text, xb - xa - 2 * margin - 6, int((y1 - y0) * 0.72), stroke=1)
    dr = ImageDraw.Draw(im)
    l, t, r, b = dr.textbbox((0, 0), text, font=f, stroke_width=1)
    x = (xa + xb) / 2 - (r - l) / 2 - l
    y = (y0 + y1) / 2 - (b - t) / 2 - t
    dr.text((x, y), text, font=f, fill=tuple(spec.get('fill', [10, 10, 10])) + (255,),
            stroke_width=1, stroke_fill=tuple(spec.get('outline', [235, 235, 235])) + (255,))


# ---------------------------------------------------------------- atlases of words
def ink_boxes(im, gap=6, vgap=2):
    """Bounding boxes of ink groups (alpha > 40), merged when closer than gap px."""
    a = im.getchannel('A').point(lambda v: 255 if v > 40 else 0)
    W, H = im.size
    pa = a.load()
    # row bands
    rows = [y for y in range(H) if any(pa[x, y] for x in range(W))]
    bands = []
    if rows:
        s = p = rows[0]
        for y in rows[1:]:
            if y > p + vgap:
                bands.append((s, p + 1))
                s = y
            p = y
        bands.append((s, p + 1))
    boxes = []
    for y0, y1 in bands:
        cols = [x for x in range(W) if any(pa[x, y] for y in range(y0, y1))]
        s = p = cols[0]
        for x in cols[1:]:
            if x > p + gap:
                boxes.append((s, y0, p + 1, y1))
                s = x
            p = x
        boxes.append((s, y0, p + 1, y1))
    return boxes


def draw_atlas(im, spec):
    if 'boxes' in spec:      # explicit [x0, y0, x1, y1, text]
        boxes = [tuple(b[:4]) for b in spec['boxes']]
        texts = [b[4] for b in spec['boxes']]
    else:
        texts = spec['atlas']
        boxes = ink_boxes(im, spec.get('gap', 6), spec.get('vgap', 2))
    if len(boxes) != len(texts):
        print(f'    atlas: {len(boxes)} boxes, {len(texts)} texts', file=sys.stderr)
        return False
    fill = tuple(spec.get('fill', [255, 255, 255])) + (255,)
    outline = spec.get('outline')
    stroke = spec.get('stroke', 1 if outline else 0)
    path = {'title': F_TITLE, 'bold': F_BOLD, 'label': F_LABEL}[spec.get('font', 'bold')]
    out = im.copy()
    dr = ImageDraw.Draw(out)
    # one font size for the whole atlas: from the typical box height
    hs = sorted(y1 - y0 for (x0, y0, x1, y1), t in zip(boxes, texts) if t)
    h_ref = hs[len(hs) // 2] if hs else 12
    base = fit(path, 'НАПРУЖЖ', 10000, h_ref + 1, start=60, stroke=stroke).size
    pad = spec.get('grow', 0)
    sizes = [fit(path, t, x1 - x0 + pad, y1 - y0 + 1, start=base, stroke=stroke).size
             for (x0, y0, x1, y1), t in zip(boxes, texts) if t]
    size = min(sizes) if sizes and spec.get('uniform', False) else base
    for (x0, y0, x1, y1), text in zip(boxes, texts):
        if text is None:
            continue
        dr.rectangle((x0 - 1, y0 - 1, x1, y1), fill=(0, 0, 0, 0))
        bw = x1 - x0 + pad
        f = fit(path, text, bw, y1 - y0 + 1, start=size, stroke=stroke)
        l, t, r, b = dr.textbbox((0, 0), text, font=f, stroke_width=stroke)
        align = spec.get('align', 'center')
        if align == 'left':
            x = x0 - l
        else:
            x = (x0 + x1) / 2 - (r - l) / 2 - l
        y = (y0 + y1) / 2 - (b - t) / 2 - t
        kw = {'stroke_width': stroke, 'stroke_fill': tuple(outline) + (255,)} if outline else {}
        dr.text((x, y), text, font=f, fill=fill, **kw)
    im.paste(out, (0, 0))
    return True


# ---------------------------------------------------------------- driver
def redraw(g, spec):
    im, info = gim.gim_to_image(g)
    im = im.convert('RGBA')
    H = im.height
    if 'header' in spec and 'footer' in spec:
        draw_header(im, spec['header'], 0, H // 2)
        draw_footer(im, spec['footer'], H // 2, H)
    elif 'header' in spec:
        draw_header(im, spec['header'], 0, H)
    elif 'footer' in spec:
        if not draw_footer(im, spec['footer'], 0, H):
            return None
    elif 'sprite' in spec:
        render_sprite(im, spec)
    elif 'plate' in spec:
        draw_plate(im, spec['plate'], spec)
    elif 'atlas' in spec or 'boxes' in spec:
        if not draw_atlas(im, spec):
            return None
    else:
        return None
    return gim.image_to_gim(g, im)


def transform(d, specs, done, cache):
    """Return d with every GIM that has a spec redrawn (walks XBB / @ANA / GIM)."""
    if d[:4] == b'MIG.':
        k = ghash(d)
        if k in specs:
            if k not in cache:
                cache[k] = redraw(d, specs[k]) or d
            done.append(k)
            return cache[k]
        return d
    if d[:4] == b'@ANA':
        out = bytearray(d)
        for off, size, _ in gim.ana_entries(d):
            new = transform(d[off:off + size], specs, done, cache)
            assert len(new) == size
            out[off:off + size] = new
        return bytes(out)
    return d


def preview(keys, out_path):
    """Before/after sheet for checking."""
    specs = load_specs()
    allp = os.path.join(ROOT, 'work', 'png', 'all')
    rows = []
    for k in keys:
        cand = None
        for f in glob.glob(os.path.join(ROOT, 'work', 'png', 'all', k + '.png')):
            cand = f
        if not cand:
            continue
        rows.append(k)
    import gzip  # noqa: F401
    idx = json.load(open(os.path.join(allp, 'index.json')))
    from build import DATA  # noqa: E402
    ims = []
    for k in rows:
        rel, path = idx[k]['where'][0]
        raw = open(os.path.join(DATA, *rel.split('/')), 'rb').read()
        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        for name, g in gim.find_gims(raw):
            if ghash(g) == k:
                new = redraw(g, specs[k])
                a, _ = gim.gim_to_image(g)
                b, _ = gim.gim_to_image(new) if new else (a, None)
                ims.append((k, a, b))
                break
    W = max([512] + [a.width for _, a, _ in ims])
    H = sum(a.height * 2 + 16 for _, a, _ in ims) or 1
    sheet = Image.new('RGB', (W, H), (70, 70, 95))
    dr = ImageDraw.Draw(sheet)
    y = 0
    for k, a, b in ims:
        dr.text((2, y), k, fill=(255, 255, 0))
        sheet.paste(a, (0, y + 10), a)
        sheet.paste(b, (0, y + 12 + a.height), b)
        y += a.height * 2 + 16
    sheet.save(out_path)


if __name__ == '__main__':
    keys = sys.argv[2:] or list(load_specs())
    preview(keys, sys.argv[1])
