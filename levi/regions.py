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
    'hair':      ('hair', 'hair_tip', 'flower'),   # flowers are white hair ornaments
    'dress':     ('dress', 'dress_mint', 'sleeve', 'cuff'),
    'green':     ('green', 'leaf', 'sleeve_dark', 'eye'),
    'petticoat': ('petticoat',),
    'shoe':      ('shoe',),
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


# Tiny face decals whose colours collide with bigger zones (the iris green is
# within a few dE of the mint hair tips); left out of reference classification.
CLASSIFY_SKIP = ('eye', 'mouth')


def palette_samples():
    """[(label, sRGB)] for every palette base/shade and their midpoint."""
    out = []
    for key, pal in spec.PALETTE.items():
        if key in CLASSIFY_SKIP:
            continue
        b, s = hex_rgb(pal['base']), hex_rgb(pal['shade'])
        for c in (b, s, (b + s) / 2):
            out.append((LABEL[REGION_OF_KEY[key]], c))
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
    # Everything green/dark below the ankles (shoe, ankle leaves and laces)
    # belongs to the shoes; above that, a dark green is trim, not shoe.
    feet = rows > row_of(L['ankle_z']) - 20
    greenish = (labels == LABEL['green']) | (labels == LABEL['shoe'])
    labels[greenish & feet] = LABEL['shoe']
    labels[greenish & ~feet] = LABEL['green']
    labels[(labels == UNKNOWN) & feet] = LABEL['shoe']
    # Pale pixels between the laces at the ankles are skin, not cloth or hair.
    pale = (labels == LABEL['dress']) | (labels == LABEL['hair'])
    labels[pale & feet] = LABEL['skin']

    labels[~mask] = BG
    labels = _majority(labels, SMOOTH_RADIUS)
    labels[~mask] = BG
    return labels


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
