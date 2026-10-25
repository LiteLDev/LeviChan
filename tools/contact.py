"""Tile renders into labelled contact sheets (bpy image IO + numpy only).

    blender -b --factory-startup -P tools/contact.py -- --out sheet.png [--cols 3] [--scale 0.5]
            [--crop] [--labels a,b,c] img1.png img2.png ...

Images are composited over white, optionally cropped to the union of their
non-transparent columns (--crop: the panels are mostly empty margin), scaled
by an integer box filter (--scale 0.5 = 2x2 average) and laid out row-major
with a caption strip under each tile (a built-in 5x7 bitmap font, so no PIL).
Also imported by render.py (turntable sheet) and used by tools/review.py.
"""
import argparse
import os
import sys

import numpy as np

# 5x7 bitmap glyphs: 7 space-separated rows of 5 columns, '#' = ink.
# Lower case prints as upper; unknown characters print as a space.
_FONT_SRC = {
    'A': '.###. #...# #...# ##### #...# #...# #...#',
    'B': '####. #...# #...# ####. #...# #...# ####.',
    'C': '.###. #...# #.... #.... #.... #...# .###.',
    'D': '####. #...# #...# #...# #...# #...# ####.',
    'E': '##### #.... #.... ####. #.... #.... #####',
    'F': '##### #.... #.... ####. #.... #.... #....',
    'G': '.###. #...# #.... #.### #...# #...# .####',
    'H': '#...# #...# #...# ##### #...# #...# #...#',
    'I': '.###. ..#.. ..#.. ..#.. ..#.. ..#.. .###.',
    'J': '..### ...#. ...#. ...#. ...#. #..#. .##..',
    'K': '#...# #..#. #.#.. ##... #.#.. #..#. #...#',
    'L': '#.... #.... #.... #.... #.... #.... #####',
    'M': '#...# ##.## #.#.# #.#.# #...# #...# #...#',
    'N': '#...# ##..# #.#.# #..## #...# #...# #...#',
    'O': '.###. #...# #...# #...# #...# #...# .###.',
    'P': '####. #...# #...# ####. #.... #.... #....',
    'Q': '.###. #...# #...# #...# #.#.# #..#. .##.#',
    'R': '####. #...# #...# ####. #.#.. #..#. #...#',
    'S': '.#### #.... #.... .###. ....# ....# ####.',
    'T': '##### ..#.. ..#.. ..#.. ..#.. ..#.. ..#..',
    'U': '#...# #...# #...# #...# #...# #...# .###.',
    'V': '#...# #...# #...# #...# #...# .#.#. ..#..',
    'W': '#...# #...# #...# #.#.# #.#.# #.#.# .#.#.',
    'X': '#...# #...# .#.#. ..#.. .#.#. #...# #...#',
    'Y': '#...# #...# .#.#. ..#.. ..#.. ..#.. ..#..',
    'Z': '##### ....# ...#. ..#.. .#... #.... #####',
    '0': '.###. #...# #..## #.#.# ##..# #...# .###.',
    '1': '..#.. .##.. ..#.. ..#.. ..#.. ..#.. .###.',
    '2': '.###. #...# ....# ...#. ..#.. .#... #####',
    '3': '####. ....# ....# .###. ....# ....# ####.',
    '4': '...#. ..##. .#.#. #..#. ##### ...#. ...#.',
    '5': '##### #.... ####. ....# ....# #...# .###.',
    '6': '..##. .#... #.... ####. #...# #...# .###.',
    '7': '##### ....# ...#. ..#.. .#... .#... .#...',
    '8': '.###. #...# #...# .###. #...# #...# .###.',
    '9': '.###. #...# #...# .#### ....# ...#. .##..',
    '_': '..... ..... ..... ..... ..... ..... #####',
    '-': '..... ..... ..... .###. ..... ..... .....',
    '.': '..... ..... ..... ..... ..... .##.. .##..',
    ',': '..... ..... ..... ..... .##.. ..#.. .#...',
    '/': '....# ....# ...#. ..#.. .#... #.... #....',
    '|': '..#.. ..#.. ..#.. ..#.. ..#.. ..#.. ..#..',
    '(': '...#. ..#.. .#... .#... .#... ..#.. ...#.',
    ')': '.#... ..#.. ...#. ...#. ...#. ..#.. .#...',
    ':': '..... .##.. .##.. ..... .##.. .##.. .....',
    '+': '..... ..#.. ..#.. ##### ..#.. ..#.. .....',
    '=': '..... ..... ##### ..... ##### ..... .....',
    ' ': '..... ..... ..... ..... ..... ..... .....',
}
FONT = {k: np.array([[c == '#' for c in row] for row in v.split()], dtype=bool)
        for k, v in _FONT_SRC.items()}
CAPTION_PX = 26   # caption strip height under each tile
TEXT_SCALE = 2


def load(path):
    """PNG -> float32 RGBA (H, W, 4), row 0 = top."""
    import bpy
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = 'sRGB'
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1]


def save(path, a):
    """float RGB(A) (H, W, 3|4), row 0 = top -> 8-bit PNG."""
    import bpy
    h, w = a.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :a.shape[2]] = np.clip(a, 0, 1)
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    img.pixels.foreach_set(np.ascontiguousarray(rgba[::-1]).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save()
    bpy.data.images.remove(img)


def over_white(a):
    if a.shape[2] == 3:
        return a
    al = a[..., 3:4]
    return a[..., :3] * al + (1 - al)


def content_cols(images, margin=16):
    """(c0, c1) column range covering every image's non-transparent pixels
    (images without transparency are ignored), or None."""
    cols = None
    for a in images:
        if a.shape[2] < 4 or (a[..., 3] > 0.99).all():
            continue
        used = np.nonzero((a[..., 3] > 0.01).any(0))[0]
        if used.size:
            lo, hi = int(used[0]), int(used[-1]) + 1
            cols = (lo, hi) if cols is None else (min(cols[0], lo), max(cols[1], hi))
    if cols is None:
        return None
    w = images[0].shape[1]
    return max(0, cols[0] - margin), min(w, cols[1] + margin)


def shrink(a, scale):
    step = max(1, int(round(1.0 / scale)))
    if step == 1:
        return a
    h, w = (a.shape[0] // step) * step, (a.shape[1] // step) * step
    return a[:h, :w].reshape(h // step, step, w // step, step, a.shape[2]).mean((1, 3))


def draw_text(img, text, x, y, scale=TEXT_SCALE, color=(0.1, 0.1, 0.1)):
    """Draw `text` with the bitmap font into img (H, W, 3) at top-left (x, y)."""
    for ch in text.upper():
        g = FONT.get(ch, FONT[' '])
        g = np.kron(g, np.ones((scale, scale), dtype=bool))
        gh, gw = g.shape
        if x + gw > img.shape[1] or y + gh > img.shape[0]:
            break
        img[y:y + gh, x:x + gw][g] = color
        x += 6 * scale
    return img


def tile(images, cols, labels=None, scale=1.0, crop=False, gap=6, title=None):
    """Lay out images (RGBA/RGB float, row 0 = top) row-major in `cols` columns
    with captions. With crop, every tile is cut to the union of the images'
    content columns, so all tiles keep the same scale and framing."""
    labels = list(labels or [])
    if crop:
        cr = content_cols(images)
        if cr:
            images = [a[:, cr[0]:cr[1]] for a in images]
    tiles = [shrink(over_white(a), scale) for a in images]
    th = max(t.shape[0] for t in tiles)
    tw = max(t.shape[1] for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    top = CAPTION_PX if title else 0
    H = top + rows * (th + CAPTION_PX + gap) + gap
    W = cols * (tw + gap) + gap
    sheet = np.full((H, W, 3), 0.82, dtype=np.float32)
    if title:
        draw_text(sheet, title, gap, 6)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        y = top + gap + r * (th + CAPTION_PX + gap)
        x = gap + c * (tw + gap)
        sheet[y:y + th, x:x + tw] = 1.0
        sheet[y:y + t.shape[0], x:x + t.shape[1]] = t
        sheet[y + th:y + th + CAPTION_PX, x:x + tw] = 1.0
        if i < len(labels) and labels[i]:
            draw_text(sheet, labels[i], x + 4, y + th + (CAPTION_PX - 7 * TEXT_SCALE) // 2)
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--cols', type=int, default=3)
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--crop', action='store_true')
    ap.add_argument('--labels', default='', help='comma-separated captions (default: file names)')
    ap.add_argument('--title', default='')
    ap.add_argument('images', nargs='+')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    labels = args.labels.split(',') if args.labels else \
        [os.path.splitext(os.path.basename(p))[0] for p in args.images]
    sheet = tile([load(p) for p in args.images], args.cols, labels, args.scale, args.crop,
                 title=args.title or None)
    save(args.out, sheet)
    print('SHEET', args.out, f'{sheet.shape[1]}x{sheet.shape[0]}')


if __name__ == '__main__':
    main()
