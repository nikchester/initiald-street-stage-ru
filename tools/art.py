"""Drawing helpers for Russian menu graphics."""
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONTS = r'C:\Windows\Fonts'
TITLE_FONT = FONTS + r'\seguibli.ttf'   # Segoe UI Black Italic
SMALL_FONT = FONTS + r'\tahomabd.ttf'   # Tahoma Bold
HEAD_FONT = FONTS + r'\seguibli.ttf'

WHITE = (255, 255, 255, 255)
YELLOW = (255, 210, 0, 255)
RED = (230, 0, 10, 255)
BLACK = (0, 0, 0, 255)


def font(path, size):
    return ImageFont.truetype(path, size)


def text_mask(text, fnt, stroke=0, size=None):
    """Return L-mode mask of text tightly cropped (incl. stroke)."""
    dr = ImageDraw.Draw(Image.new('L', (1, 1)))
    l, t, r, b = dr.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    im = Image.new('L', (r - l + 4, b - t + 4), 0)
    ImageDraw.Draw(im).text((2 - l, 2 - t), text, font=fnt, fill=255, stroke_width=stroke, stroke_fill=255)
    return im


def fit_font(path, text, max_w, max_h, start=60, stroke=0):
    for size in range(start, 6, -1):
        f = font(path, size)
        m = text_mask(text, f, stroke)
        bb = m.getbbox()
        if bb and bb[2] - bb[0] <= max_w and bb[3] - bb[1] <= max_h:
            return f
    return font(path, 7)


def title_layers(segments, box, path=TITLE_FONT, stroke=3):
    """segments: list of (text, accent:bool, scale). box: (x0, y0, x1, y1) target area.
    Returns dict of L masks (full canvas size is set by caller) positioned in box:
      fill_white, fill_red, outline (black stroke), shape (union for glow)."""
    x0, y0, x1, y1 = box
    max_w, max_h = x1 - x0, y1 - y0
    full = ''.join(s for s, _, _ in segments)
    base = fit_font(path, full, max_w - 2 * stroke, max_h - 2 * stroke, stroke=stroke)
    # measure each segment with its own scale; baseline-align
    parts = []
    for s, accent, scale in segments:
        f = font(path, max(7, int(base.size * scale)))
        parts.append((s, accent, f))
    dr = ImageDraw.Draw(Image.new('L', (1, 1)))
    widths = [dr.textlength(s, font=f) for s, _, f in parts]
    total = sum(widths)
    asc = max(f.getmetrics()[0] for _, _, f in parts)
    # vertical: center capital height of base font in box
    cap_t, cap_b = dr.textbbox((0, 0), 'Н', font=base)[1::2]
    cap_h = cap_b - cap_t
    baseline = y0 + (max_h + cap_h) // 2
    x = x0 + (max_w - total) / 2
    return parts, widths, x, baseline


def render_title(size, segments, box, glow=False, text=True):
    """Big menu title like the originals: white letters, black outline, red accent.
    glow=True adds an orange glow on black (the 'selected' variants)."""
    W, H = size
    parts, widths, x, baseline = title_layers(segments, box)
    white = Image.new('L', size, 0)
    red = Image.new('L', size, 0)
    outline = Image.new('L', size, 0)
    for (s, accent, f), w in zip(parts, widths):
        asc = f.getmetrics()[0]
        pos = (x, baseline - asc)
        ImageDraw.Draw(outline).text(pos, s, font=f, fill=255, stroke_width=4, stroke_fill=255)
        ImageDraw.Draw(red if accent else white).text(pos, s, font=f, fill=255)
        x += w
    shape = ImageChops.lighter(outline, white)
    if not glow:
        out = Image.new('RGBA', size, (0, 0, 0, 0))
        # drop shadow
        sh = Image.new('RGBA', size, (0, 0, 0, 160))
        out.paste(sh, (3, 3), outline)
        out.paste(Image.new('RGBA', size, BLACK), (0, 0), outline)
        # white rim around red accent letters
        rim = red.filter(ImageFilter.MaxFilter(5))
        out.paste(Image.new('RGBA', size, WHITE), (0, 0), rim)
        out.paste(Image.new('RGBA', size, WHITE), (0, 0), white)
        out.paste(Image.new('RGBA', size, RED), (0, 0), red)
        return out
    # glow variant: black opaque background, orange halo, optional white-hot text
    out = Image.new('RGBA', size, BLACK)
    core = ImageChops.lighter(white, red).filter(ImageFilter.MaxFilter(5))
    halo_big = core.filter(ImageFilter.GaussianBlur(7))
    halo_mid = core.filter(ImageFilter.GaussianBlur(3))
    out.paste(Image.new('RGBA', size, (200, 60, 0, 255)), (0, 0), halo_big.point(lambda v: min(255, v * 3)))
    out.paste(Image.new('RGBA', size, (255, 150, 30, 255)), (0, 0), halo_mid.point(lambda v: min(255, v * 2)))
    out.paste(Image.new('RGBA', size, (255, 230, 170, 255)), (0, 0), core)
    if text:
        letters = ImageChops.lighter(white, red)
        out.paste(Image.new('RGBA', size, (255, 255, 255, 255)), (0, 0), letters)
    return out


def render_lines(size, lines, x=94, y=28, pitch=11, fnt=None):
    """Small description text. lines: list of strings; text inside «...» is yellow."""
    fnt = fnt or font(SMALL_FONT, 11)
    out = Image.new('RGBA', size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(out)
    for i, line in enumerate(lines):
        cx = x
        yellow = False
        buf = ''
        segs = []
        for ch in line:
            if ch == '«':
                if buf:
                    segs.append((buf, yellow))
                buf, yellow = ch, True
            elif ch == '»' and yellow:
                segs.append((buf + ch, True))
                buf, yellow = '', False
            else:
                buf += ch
        if buf:
            segs.append((buf, yellow))
        for s, yl in segs:
            dr.text((cx, y + i * pitch - 1), s, font=fnt, fill=YELLOW if yl else WHITE)
            cx += dr.textlength(s, font=fnt)
        if cx > size[0] - 4:
            print(f'  WARNING: line too wide ({cx:.0f}px): {line}')
    return out


def column_fill(im, x_src, box):
    """Erase box by repeating the pixel column x_src (for vertical gradients)."""
    x0, y0, x1, y1 = box
    col = im.crop((x_src, y0, x_src + 1, y1))
    for x in range(x0, x1):
        im.paste(col, (x, y0))


def pattern_fill(im, box, period, src_dx):
    """Erase box by copying pixels shifted left by src_dx (src_dx multiple of pattern period)."""
    x0, y0, x1, y1 = box
    assert src_dx % period == 0
    patch = im.crop((x0 - src_dx, y0, x1 - src_dx, y1))
    im.paste(patch, (x0, y0))
