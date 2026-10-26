"""Colour regions of the reference and of renders (pure numpy, no bpy).

A region groups palette keys that belong to one visual zone of the sheet.
tools/prep_ref.py segments the reference panels into regions by colour
(plus a few spatial priors from spec.L) and commits ref/<view>_regions.png;
render.py writes an exact <view>_regions.png from the materials' palette keys;
tools/compare.py reports per-region IoU and colour error between the two.
"""
import numpy as np

from . import spec

# Region -> palette keys. Every spec.PALETTE key belongs to exactly one region.
REGIONS = {
    'skin':      ('skin', 'mouth'),
    'hair':      ('hair', 'hair_tip', 'flower', 'flower_center'),   # flowers are hair ornaments
    'dress':     ('dress', 'dress_mint', 'sleeve', 'cuff'),
    'green':     ('green', 'leaf', 'sleeve_dark', 'eye'),
    'petticoat': ('petticoat',),
    'shoe':      ('shoe', 'sole'),
}
REGION_NAMES = tuple(REGIONS)
REGION_OF_KEY = {k: r for r, ks in REGIONS.items() for k in ks}

# Label ids: 0 = background, 1.. = REGION_NAMES order, UNKNOWN = unclassified.
BG = 0
UNKNOWN = len(REGION_NAMES) + 1
LABEL = {r: i + 1 for i, r in enumerate(REGION_NAMES)}

# Flat colours (8-bit sRGB) used to encode labels in *_regions.png files.
LABEL_RGB = {
    BG: (0, 0, 0),
    LABEL['skin']: (240, 150, 110),
    LABEL['hair']: (110, 130, 240),
    LABEL['dress']: (235, 235, 190),
    LABEL['green']: (30, 170, 60),
    LABEL['petticoat']: (240, 90, 170),
    LABEL['shoe']: (10, 80, 30),
    UNKNOWN: (128, 128, 128),
}

# Max CIE76 distance from a palette colour for a reference pixel to be
# classified at all (anything further, e.g. dark line art, is UNKNOWN).
MAX_DE = 22.0
SMOOTH_RADIUS = 2      # majority filter radius (px) applied to the reference
# The sheet's whites differ mostly in tint (hair is neutral grey, the dress and
# sleeves are yellow-green), while painted shading moves lightness a lot, so
# lightness differences count 1/L_WEIGHT as much when classifying.
L_WEIGHT = 3.0


def hex_rgb(hex_str):
    h = hex_str.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def srgb_to_lab(rgb):
    """sRGB (..., 3) in 0..1 -> CIE L*a*b* (D65)."""
    c = np.asarray(rgb, dtype=np.float64)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e(a_rgb, b_rgb):
    """CIE76 colour difference between two sRGB arrays (..., 3)."""
    return np.linalg.norm(srgb_to_lab(a_rgb) - srgb_to_lab(b_rgb), axis=-1)


# Tiny decals whose colours collide with bigger zones (the iris green is
# within a few dE of the mint hair tips; the tan soles are close to greyed
# line art); left out of reference classification. Unclassified pixels at the
# feet become shoe anyway.
CLASSIFY_SKIP = ('eye', 'mouth', 'flower_center', 'sole')


# Palette pairs painted as a continuous gradient on the sheet (the hair fades
# from white to mint toward the tips). Their in-between tints are sampled too,
# so a half-mint strand reads as hair rather than as pale mint cloth.
GRADIENTS = (('hair', 'hair_tip'),)
GRADIENT_STEPS = (0.15, 0.3, 0.45, 0.6, 0.75)


def palette_samples():
    """[(label, sRGB)] for every sheet palette base/shade and their midpoint,
    plus the in-between tints of each GRADIENTS pair. Uses spec.SHEET_PALETTE
    (the sheet's measured colours), not the tuned render palette, so the
    reference regions do not move when look-dev retunes spec.PALETTE."""
    pal = spec.SHEET_PALETTE
    out = []
    for key, p in pal.items():
        if key in CLASSIFY_SKIP:
            continue
        b, s = hex_rgb(p['base']), hex_rgb(p['shade'])
        for c in (b, s, (b + s) / 2):
            out.append((LABEL[REGION_OF_KEY[key]], c))
    for ka, kb in GRADIENTS:
        for tone in ('base', 'shade'):
            a, b = hex_rgb(pal[ka][tone]), hex_rgb(pal[kb][tone])
            for t in GRADIENT_STEPS:
                region = REGION_OF_KEY[ka] if t < 0.5 else REGION_OF_KEY[kb]
                out.append((LABEL[region], a + (b - a) * t))
    return out


# Line-bounded voting. The pale regions (white hair, cream cloth, skin) share
# tints wherever the painting shades or highlights them, so per-pixel colour
# alone speckles them. The sheet's line art encloses each painted area, so
# the pale pixels are grouped into components bounded by strokes and each
# component takes its majority pale label. Components bigger than
# VOTE_MAX_PX (strokes with gaps that let zones leak together) or smaller
# than VOTE_MIN_PX keep their per-pixel labels.
PALE = ('skin', 'hair', 'dress')
LINE_DROP = 10.0      # L* below the 5x5 local maximum that marks a stroke pixel
VOTE_MIN_PX = 40
VOTE_MAX_PX = 25000
VOTE_MIN_SHARE = 0.55  # the winning label's share of the component


def stroke_mask(rgb):
    """Pixels on dark line art: noticeably darker than their 5x5 neighbourhood."""
    lum = srgb_to_lab(rgb)[..., 0]
    h, w = lum.shape
    pad = np.pad(lum, 2, mode='edge')
    mx = lum.copy()
    for dy in range(5):
        for dx in range(5):
            np.maximum(mx, pad[dy:dy + h, dx:dx + w], out=mx)
    return lum < mx - LINE_DROP


def components(allowed, diagonal=False):
    """4-connected (8 with diagonal=True) component ids (int32, -1 outside
    `allowed`), pure numpy: min-label propagation with pointer jumping.
    Works on the bounding box of `allowed` only (a region is a small part of
    the panel), so ids are unique but not pixel indices of the full image."""
    rows = np.flatnonzero(allowed.any(1))
    if not rows.size:
        return np.full(allowed.shape, -1, dtype=np.int32)
    cols = np.flatnonzero(allowed.any(0))
    y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    if (y1 - y0, x1 - x0) != allowed.shape:
        out = np.full(allowed.shape, -1, dtype=np.int32)
        out[y0:y1, x0:x1] = components(allowed[y0:y1, x0:x1], diagonal)
        return out
    h, w = allowed.shape
    big = np.int32(h * w)
    lab = np.where(allowed, np.arange(h * w, dtype=np.int32).reshape(h, w), big)
    while True:
        prev = lab
        m = lab.copy()
        m[1:] = np.minimum(m[1:], np.where(allowed[:-1], lab[:-1], big))
        m[:-1] = np.minimum(m[:-1], np.where(allowed[1:], lab[1:], big))
        m[:, 1:] = np.minimum(m[:, 1:], np.where(allowed[:, :-1], lab[:, :-1], big))
        m[:, :-1] = np.minimum(m[:, :-1], np.where(allowed[:, 1:], lab[:, 1:], big))
        if diagonal:
            m[1:, 1:] = np.minimum(m[1:, 1:], np.where(allowed[:-1, :-1], lab[:-1, :-1], big))
            m[:-1, :-1] = np.minimum(m[:-1, :-1], np.where(allowed[1:, 1:], lab[1:, 1:], big))
            m[1:, :-1] = np.minimum(m[1:, :-1], np.where(allowed[:-1, 1:], lab[:-1, 1:], big))
            m[:-1, 1:] = np.minimum(m[:-1, 1:], np.where(allowed[1:, :-1], lab[1:, :-1], big))
        m = np.where(allowed, m, big)
        flat = np.append(m.ravel(), big)
        for _ in range(8):   # pointer jumping: follow each label to its root
            flat = np.minimum(flat, flat[np.minimum(flat, big)])
        lab = flat[:-1].reshape(h, w)
        if (lab == prev).all():
            break
    return np.where(allowed, lab, -1)


def vote_pale(labels, rgb):
    """Give each line-bounded pale component its majority pale label."""
    pale_ids = np.array([LABEL[r] for r in PALE], dtype=np.uint8)
    pale = np.isin(labels, pale_ids)
    comp = components(pale & ~stroke_mask(rgb))
    ids = comp[comp >= 0]
    if not ids.size:
        return labels
    uniq, inv = np.unique(ids, return_inverse=True)
    lbl = labels[comp >= 0]
    counts = np.zeros((len(uniq), len(pale_ids)), dtype=np.int64)
    for j, k in enumerate(pale_ids):
        counts[:, j] = np.bincount(inv, weights=(lbl == k), minlength=len(uniq))
    size = counts.sum(1)
    win = counts.argmax(1)
    share = counts.max(1) / np.maximum(size, 1)
    ok = (size >= VOTE_MIN_PX) & (size <= VOTE_MAX_PX) & (share >= VOTE_MIN_SHARE)
    new = np.where(ok[inv], pale_ids[win][inv], lbl)
    out = labels.copy()
    out[comp >= 0] = new
    return out


# Enclosed islands. After voting, a small connected patch of one pale label
# that is (almost) entirely surrounded by another region is a painted
# highlight or tint of that region, not a separate zone: the palest mint hair
# lobes over the back skirt read as dress, small skin highlights read as
# dress. Line art (UNKNOWN) around the patch is ignored; a patch touching the
# background is never relabelled.
ISLAND_MAX_PX = 1500
ISLAND_MIN_SHARE = 0.85


def fill_islands(labels, max_px=ISLAND_MAX_PX, min_share=ISLAND_MIN_SHARE):
    """Relabel small pale components enclosed by one other region."""
    out = labels.copy()
    n_lab = UNKNOWN + 1
    # Near the background, through the outline stroke (which is UNKNOWN).
    near_bg = dilate(labels == BG, 4)
    for name in PALE:
        k = LABEL[name]
        # Each label sees the previous labels' relabelling, so nested islands
        # resolve consistently. Look through the line art: a stroke pixel
        # counts as the region its neighbourhood mostly belongs to.
        near = np.where(out == UNKNOWN, _majority(out, 3), out)
        comp = components(out == k)
        ids = comp[comp >= 0]
        if not ids.size:
            continue
        uniq, inv = np.unique(ids, return_inverse=True)
        size = np.bincount(inv, minlength=len(uniq))
        idx = np.full(comp.shape, -1, dtype=np.int64)
        idx[comp >= 0] = inv
        # border histogram: (component, neighbour label) over 4-neighbour edges
        hist = np.zeros((len(uniq), n_lab), dtype=np.int64)
        for a, b in ((idx[1:], near[:-1]), (idx[:-1], near[1:]),
                     (idx[:, 1:], near[:, :-1]), (idx[:, :-1], near[:, 1:])):
            m = (a >= 0) & (b != k)
            np.add.at(hist, (a[m], b[m].astype(np.int64)), 1)
        # components within a stroke's width of the background, or on the
        # panel edge, count as touching the background
        edge = np.unique(np.concatenate([idx[0], idx[-1], idx[:, 0], idx[:, -1], idx[near_bg]]))
        hist[edge[edge >= 0], BG] += 1
        known = hist.copy()
        known[:, UNKNOWN] = 0
        total = known.sum(1)
        best = known.argmax(1)
        share = known.max(1) / np.maximum(total, 1)
        ok = ((size <= max_px) & (hist[:, BG] == 0) & (total > 0) & (share >= min_share)
              & (best != BG) & (best != k))
        if ok.any():
            sel = (idx >= 0) & ok[np.maximum(idx, 0)]
            out[sel] = best[idx[sel]]
    return out


def fold_feet(labels):
    """Everything green below the ankles (ankle leaves, laces) counts as shoe.
    Applied to the reference and to render labels alike, so laces score the
    same in both."""
    rows = np.arange(labels.shape[0])[:, None]
    feet = rows > spec.SHEET_GROUND_Y - spec.L['ankle_z'] * spec.PX_PER_M - 20
    out = labels.copy()
    out[(labels == LABEL['green']) & feet] = LABEL['shoe']
    return out


def _majority(labels, radius):
    """Majority vote among region labels only: background and UNKNOWN never
    win, so thin strands near the silhouette and line art next to a region
    are absorbed into the region rather than erased. Pixels with no region
    neighbour keep their label."""
    h, w = labels.shape
    n = len(REGION_NAMES)
    counts = np.zeros((n, h, w), dtype=np.int16)
    pad = np.pad(labels, radius, mode='edge')
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            win = pad[radius + dy:radius + dy + h, radius + dx:radius + dx + w]
            for k in range(n):
                counts[k] += win == k + 1
    out = (counts.argmax(0) + 1).astype(np.uint8)
    none = counts.max(0) == 0
    out[none] = labels[none]
    return out


def classify_reference(rgb, mask, view):
    """Label a reference panel (H, W, 3 sRGB, row 0 = top) by nearest palette
    colour inside `mask`, then resolve colour-ambiguous pairs with spatial
    priors from spec.L and clean up with a majority filter."""
    h, w = mask.shape
    wl = np.array([1.0 / L_WEIGHT, 1.0, 1.0])
    lab = srgb_to_lab(rgb) * wl
    samples = palette_samples()
    s_lab = srgb_to_lab(np.array([c for _, c in samples])) * wl
    s_lbl = np.array([l for l, _ in samples], dtype=np.uint8)
    best_d = np.full((h, w), np.inf)
    labels = np.full((h, w), UNKNOWN, dtype=np.uint8)
    for sl, sc in zip(s_lbl, s_lab):
        d = np.linalg.norm(lab - sc, axis=-1)
        closer = d < best_d
        best_d[closer] = d[closer]
        labels[closer] = sl
    labels[best_d > MAX_DE] = UNKNOWN
    labels[~mask] = BG
    # Vote before the spatial priors below, so they have the last word.
    labels = vote_pale(labels, rgb)
    labels = fill_islands(labels)

    rows = np.arange(h)[:, None].repeat(w, 1)
    cols = np.arange(w)[None, :].repeat(h, 0)
    row_of = lambda z: spec.SHEET_GROUND_Y - z * spec.PX_PER_M  # noqa: E731
    L = spec.L
    # Skin and petticoat pinks are within a few dE of each other: the
    # petticoat only shows in a band around the skirt hem, and inside that
    # band the legs are the central columns below the centre-front hem.
    pink = (labels == LABEL['skin']) | (labels == LABEL['petticoat'])
    band = (rows > row_of(L['skirt_hem_side_z']) - 40) & (rows < row_of(L['petticoat_hem_z']) + 30)
    leg_x = L['leg_center_x'] * spec.PX_PER_M
    leg_r = (L['thigh_half_w'] + 0.008) * spec.PX_PER_M
    legs = (np.abs(np.abs(cols - w / 2) - leg_x) < leg_r) & (rows > row_of(L['skirt_hem_z']))
    if view == 'side':   # legs overlap at the panel centre in profile
        legs = (np.abs(cols - w / 2) < leg_x) & (rows > row_of(L['skirt_hem_z']))
    labels[pink & band & ~legs] = LABEL['petticoat']
    labels[pink & ~(band & ~legs)] = LABEL['skin']
    feet = rows > row_of(L['ankle_z']) - 20
    labels = fold_feet(labels)
    # Above the ankles a dark green is trim, not shoe.
    labels[(labels == LABEL['shoe']) & ~feet] = LABEL['green']
    labels[(labels == UNKNOWN) & feet] = LABEL['shoe']
    # Pale pixels between the laces at the ankles are skin, not cloth or hair.
    pale = (labels == LABEL['dress']) | (labels == LABEL['hair'])
    labels[pale & feet] = LABEL['skin']

    labels[~mask] = BG
    labels = _majority(labels, SMOOTH_RADIUS)
    labels[~mask] = BG
    return labels


def dilate(m, radius):
    """Binary dilation by a (2r+1)^2 square."""
    out = m.copy()
    h, w = m.shape
    pad = np.pad(m, radius)
    for dy in range(2 * radius + 1):
        for dx in range(2 * radius + 1):
            out |= pad[dy:dy + h, dx:dx + w]
    return out


TOL_PX = 2


def tolerant_overlap(a, b, radius=TOL_PX):
    """Overlap of two masks that forgives misplacement up to `radius` px:
    the share of a's and b's pixels lying within `radius` of the other mask.
    For thin zones (ribbons, laces) a 1-2 px offset halves the plain IoU while
    the shapes still line up; this separates misalignment from missing parts."""
    na, nb = int(a.sum()), int(b.sum())
    if na + nb == 0:
        return 1.0
    return float(((a & dilate(b, radius)).sum() + (b & dilate(a, radius)).sum()) / (na + nb))


def shade_share(rgb, labels, region, palette=None, max_de=15.0):
    """Share of a region's pixels painted in a shade tone: each pixel is
    matched to the nearest base/shade colour of the region's palette keys
    (pixels further than max_de from all, e.g. line art, are skipped).
    palette: spec.PALETTE (default, for renders) or spec.SHEET_PALETTE (for
    the reference). Returns (share, n_matched) or (nan, 0)."""
    shade, ok = shade_mask(rgb, labels, region, palette, max_de)
    if not ok.any():
        return float('nan'), 0
    return float(shade.sum() / ok.sum()), int(ok.sum())


def shade_mask(rgb, labels, region, palette=None, max_de=15.0):
    """(shade, matched) pixel masks of a region: matched = within max_de of a
    base/shade colour of the region's keys, shade = nearest one is a shade."""
    palette = spec.PALETTE if palette is None else palette
    m = labels == LABEL[region]
    shade = np.zeros(labels.shape, dtype=bool)
    ok = np.zeros(labels.shape, dtype=bool)
    if not m.any():
        return shade, ok
    cols = np.array([hex_rgb(palette[k][t]) for k in REGIONS[region] for t in ('base', 'shade')])
    d = np.linalg.norm(srgb_to_lab(rgb[m])[:, None] - srgb_to_lab(cols)[None], axis=-1)
    hit = d.min(1) < max_de
    ok[m] = hit
    shade[m] = (d.argmin(1) % 2 == 1) & hit
    return shade, ok


# Small shade islands (look-dev metric, tools/review.py): connected shade
# patches of SHADE_ISLAND_MIN_PX..SHADE_ISLAND_SMALL_PX pixels inside one
# region of a render. The sheet paints shade as broad, smooth shapes, so
# isolated slivers and specks (cast-shadow acne, thin ribbons' contact
# shadows, faceted terminators, outline-hull pokes) make pale surfaces look
# chipped. Specks under 4 px and fringes that hug line art (anti-aliasing,
# within ISLAND_LINE_PX) are not counted. Only meaningful on renders (exact
# palette colours), not on the painted sheet.
SHADE_ISLAND_MIN_PX = 4
SHADE_ISLAND_SMALL_PX = 80   # ~9x9 px = 1.4 cm square at the sheet scale
ISLAND_LINE_PX = 2           # fringe width ignored next to line art


def shade_islands(rgb, labels, region, palette=None,
                  min_px=SHADE_ISLAND_MIN_PX, max_px=SHADE_ISLAND_SMALL_PX):
    """Small shade islands of a region: (count, area_px, mask of their pixels).

    Shade pixels are those nearest a shade tone (shade_mask, max_de 15);
    8-connected through each other, ignoring line art, so an island is a
    patch of shade cut off from the region's broad shade areas."""
    shade, ok = shade_mask(rgb, labels, region, palette)
    if not shade.any():
        return 0, 0, shade
    # 8-connected: a thin diagonal shade edge is one patch, not many specks.
    ids = components(shade, diagonal=True)[shade]
    uniq, inv, size = np.unique(ids, return_inverse=True, return_counts=True)
    # A patch counts only if it has a core pixel: one more than
    # ISLAND_LINE_PX px from any pixel that matches none of the region's
    # tones (line art, other regions, background). The anti-aliased fringe
    # where a pale fill meets its dark line art blends toward the shade tone
    # but hugs the line, so it never has a core; a 1 px terminator sliver out
    # in a lit area does.
    core = shade & ~dilate(~ok, ISLAND_LINE_PX)
    has_core = np.bincount(inv, weights=core[shade], minlength=len(uniq)) > 0
    small = (size >= min_px) & (size <= max_px) & has_core
    mask = np.zeros(shade.shape, dtype=bool)
    mask[shade] = small[inv]
    return int(small.sum()), int(size[small].sum()), mask


def encode(labels):
    """Label map -> sRGB float image (H, W, 3)."""
    out = np.zeros(labels.shape + (3,), dtype=np.float32)
    for k, c in LABEL_RGB.items():
        out[labels == k] = np.array(c, dtype=np.float32) / 255.0
    return out


def decode(rgb, alpha=None):
    """sRGB float image (H, W, 3) -> label map (nearest LABEL_RGB entry).
    Anti-aliased edges in rendered label images snap to the nearest label."""
    h, w = rgb.shape[:2]
    best_d = np.full((h, w), np.inf, dtype=np.float32)
    labels = np.zeros((h, w), dtype=np.uint8)
    for k, c in LABEL_RGB.items():
        d = ((rgb - np.array(c, dtype=np.float32) / 255.0) ** 2).sum(-1)
        closer = d < best_d
        best_d[closer] = d[closer]
        labels[closer] = k
    if alpha is not None:
        labels[alpha < 0.5] = BG
    return labels


def parse_regions(arg):
    """'skin,hair' -> [label ids]; raises ValueError on unknown names."""
    names = [r for r in arg.split(',') if r]
    bad = [r for r in names if r not in LABEL]
    if bad:
        raise ValueError(f'unknown region(s) {bad}; choose from {list(REGION_NAMES)}')
    return [LABEL[r] for r in names]
