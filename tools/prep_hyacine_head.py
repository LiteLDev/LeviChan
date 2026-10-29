"""Make the head asset from the 风堇 (Hyacine) PMX (round 11).

    blender -b --factory-startup -P tools/prep_hyacine_head.py -- --pmx <path.pmx>
                                     [--out assets/hyacine]

Reads the PMX with tools/pmxread.py and her face texture (颜.png, beside the
PMX) with Blender's image loader, and writes two deterministic files:

  head.npz        her face, mouth, eyes, lashes and brows in our frame
  head_atlas.png  RGBA, a derivative of 颜.png repainted to Levi's design

head.npz (metres, our frame = MMD (x, z, y) * 0.08, triangle winding reversed,
UV v up). Not aligned to Levi: levi/parts/head.py moves and warps it.

  parts             str (k,)         face, mouth, teeth, tongue, white, iris, hilite, lash
  <p>_pos           float32 (n, 3)   vertices, welded across her UV seams
  <p>_tri           int32 (m, 3)     triangles
  <p>_uv            float32 (m, 3, 2) corner UVs into head_atlas.png
  <p>_isl           int16 (m,)       for lash: which strip a triangle belongs to (LASH_KIND)
  morph_names       str (q,)         cleaned names (see RENAME, DROP)
  morph_src         str (q,)         her names
  <p>_mptr          int64 (q + 1,)   CSR over morphs: offsets of <p>'s vertices
  <p>_mvi, <p>_moff int32 / float32  vertex index, offset (m)
  bone_names / bone_head            頭, 首, 両目, 左目, 右目, 左目先, 右目先 (heads, m)
  lash_kind         str              names of the lash strip kinds

Kept from her model: the face mask 颜 without her flat ear cards (Levi keeps
his modelled ears), the mouth cavity 口 with teeth 齿 and tongue 舌, the white
cup 白目, the iris dish 目, the highlight cards 目光 (only their position; the
part rebuilds one oval) and the lash / liner / brow strips 眉睫. Dropped: her
lid shadow 目影 (alpha 0.3; the part paints an opaque one), the blush overlay
颜+, the expression decals biaoq, her hair, clothes and body.

Morphs: every vertex morph except the decal swaps (はぅ, はちゅ目, なごみ move the
eyes ~8 cm into the head to show biaoq icons) and the biaoq-only icons. Names
are cleaned: NFKC (half-width ｷﾘｯ -> キリッ, ｳｨﾝｸ２右 -> ウィンク2右), the
duplicate 笑い2 (#21, the one-eyed blink) becomes ウィンク２ and her ｳｨﾝｸ２右
ウィンク２右, trailing spaces go.

The atlas: her 颜.png (1024², RGB) with
  * the face sheet painted flat skin (Levi's palette): her forehead gradient,
    coral lids, blush, nose and jaw marks and lip tint go (the toon ramp shades;
    Levi's own marks are painted below, as functions of the 3D position on her
    face placed on Levi's head);
  * the iris tile repainted in Levi's design (ref/setting.png): green with a
    darker upper band, a rounded darker pupil, a navy rim;
  * the lash, liner and brow strips flat navy / mauve;
  * the white cup's tile white with Levi's soft blue-grey lid shadow on top;
  * alpha = the toon shading mask (1 skin, 0 unshaded decals), never transparency.
Everything outside the UV islands keeps her pixels (unused).
"""
import argparse
import json
import os
import sys
import unicodedata

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import pmxread  # noqa: E402

S = 0.08
MATS = {'face': '颜', 'mouth': '口', 'teeth': '齿', 'tongue': '舌', 'white': '白目', 'iris': '目',
        'hilite': '目光', 'lash': '眉睫'}
BONES = ('頭', '首', '両目', '左目', '右目', '左目先', '右目先')
DROP = {'はぅ', 'はちゅ目', 'なごみ', 'はぁと', '星目', '涙', '脸红', '汗颜', '111', '1111', '11+', '怒',
        '！', '？', '！！', '汗'}
EAR_X = 0.045          # m: her face islands entirely beyond this |x| are the ear cards
# where her face sits on Levi's head (eye and cheek aligned): only used to paint
# Levi's marks at the right place; the part applies the same shift
ALIGN = np.array([0.0023, -0.0509, 0.0511])
LASH_KIND = ('upper', 'lower', 'brow', 'crease', 'liner', 'flick', 'other')
TEX = 1024

# Levi's colours (ref/setting.png, sampled; spec.PALETTE skin base)
SKIN = '#FEEAE1'
NAVY = '#1B1C4D'
LOW_LASH = '#3E3A63'
BROW = '#857A92'
CREASE = '#C9A39E'
IRIS_LO, IRIS_UP, PUPIL, RIM = '#67AC80', '#5B855F', '#4F7A58', '#313855'
LID_SHADE = '#D3DCEB'
LIP_LINE = '#9C5A55'


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def our(a):
    return np.asarray(a, float)[..., [0, 2, 1]] * S


def smooth(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def extract(m):
    """{part: dict(pos, tri, uv, vi (PMX vertex per welded vertex), fvi (PMX corner vertices))}."""
    o = 0
    spans = {}
    for mt in m['mats']:
        n = mt['nidx'] // 3
        spans[mt['name']] = (o // 3, o // 3 + n)
        o += mt['nidx']
    pos_all = our(m['pos'])
    uv_all = m['uv'].copy()
    uv_all[:, 1] = 1.0 - uv_all[:, 1]
    out = {}
    for part, mat in MATS.items():
        a, b = spans[mat]
        F = m['faces'][a:b][:, ::-1].astype(np.int64)        # winding reversed (the axis swap mirrors)
        if part == 'face':
            F = F[~_ear_faces(F, pos_all)]
        key = np.round(pos_all[F.reshape(-1)] / 1e-7).astype(np.int64)
        uk, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        tri = inv.reshape(-1, 3).astype(np.int32)
        pos = np.zeros((len(uk), 3))
        pos[inv] = pos_all[F.reshape(-1)]
        pvi = np.zeros(len(uk), np.int64)
        pvi[inv] = F.reshape(-1)
        # drop degenerate triangles (welded corners)
        ok = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
        out[part] = dict(pos=pos, tri=tri[ok], uv=uv_all[F][ok], fvi=F[ok], inv=inv.reshape(-1, 3)[ok])
    return out


def _ear_faces(F, pos):
    """Faces of her ear cards: vertex-level islands (her UV-split islands) lying
    wholly beyond EAR_X."""
    n = pos.shape[0]
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for t in F:
        r = [find(int(v)) for v in t]
        for q in r[1:]:
            if q != r[0]:
                parent[q] = r[0]
    root = np.array([find(int(v)) for v in F[:, 0]])
    ear = np.zeros(len(F), bool)
    for r in np.unique(root):
        sel = root == r
        vs = np.unique(F[sel])
        if np.abs(pos[vs, 0]).min() > EAR_X:
            ear |= sel
    return ear


def clean_name(mo):
    nm = unicodedata.normalize('NFKC', mo['name']).strip()
    if mo['name'] == '笑い2' and mo['name_en'] == 'Eye_Close01':
        nm = 'ウィンク２'                 # her duplicate name: the one-eyed blink (left)
    elif nm == 'ウィンク2右':
        nm = 'ウィンク２右'
    return nm


def morphs(m, parts):
    """Cleaned vertex morphs, per part CSR offsets (welded vertices: mean of duplicates)."""
    names, src, keep = [], [], []
    for mo in m['morphs']:
        if mo['type'] != 1:
            continue
        nm = clean_name(mo)
        if nm in DROP or mo['name'].strip() in DROP:
            continue
        if nm in names:
            raise SystemExit(f'duplicate morph name after cleaning: {nm}')
        names.append(nm)
        src.append(mo['name'])
        keep.append(mo)
    luts = {}
    for p, P in parts.items():
        lut = {}
        for a, b in zip(P['fvi'].reshape(-1), P['inv'].reshape(-1)):
            lut.setdefault(int(a), int(b))
        luts[p] = lut
    out = {p: ([0], [], []) for p in parts}
    for mo in keep:
        vi = [o[0] for o in mo['offsets']]
        d = our(np.array([o[1:] for o in mo['offsets']], float))
        for p in parts:
            ptr, mvi, moff = out[p]
            lut = luts[p]
            acc = {}
            for v, dv in zip(vi, d):
                w = lut.get(int(v))
                if w is None:
                    continue
                s_ = acc.setdefault(w, [np.zeros(3), 0])
                s_[0] += dv
                s_[1] += 1
            for w in sorted(acc):
                dv = acc[w][0] / acc[w][1]
                if np.abs(dv).max() > 1e-7:
                    mvi.append(w)
                    moff.append(dv)
            ptr.append(len(mvi))
    return names, src, out


# ---------------------------------------------------------------- atlas
def raster(tri_uv, values, H=TEX, W=TEX):
    """Rasterise triangles in UV space. values: (m, 3, k) per-corner values,
    interpolated. Returns (cover (H, W) bool, field (H, W, k), tri index (H, W))."""
    k = values.shape[2]
    cover = np.zeros((H, W), bool)
    field = np.zeros((H, W, k))
    tid = -np.ones((H, W), np.int64)
    P = np.stack([tri_uv[..., 0] * W - 0.5, (1.0 - tri_uv[..., 1]) * H - 0.5], -1)   # pixel centres
    for t in range(len(P)):
        p = P[t]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0 - 1, 0), max(y0 - 1, 0)
        x1, y1 = min(x1 + 1, W - 1), min(y1 + 1, H - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        a, b, c = p
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        l1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        l2 = 1.0 - l0 - l1
        eps = 0.6 / max(abs(den) ** 0.5, 1.0)       # a half-pixel margin: no cracks along shared edges
        inside = (l0 >= -eps) & (l1 >= -eps) & (l2 >= -eps)
        if not inside.any():
            continue
        L = np.stack([l0, l1, l2], -1)[inside]
        L = np.clip(L, 0, None)
        L /= L.sum(1, keepdims=True)
        yy, xx = ys[inside], xs[inside]
        field[yy, xx] = L @ values[t]
        cover[yy, xx] = True
        tid[yy, xx] = t
    return cover, field, tid


def lash_kinds(P):
    """Classify the lash / brow strips (welded islands of 眉睫) by where they sit
    relative to the eye opening (her frame, left eye mirrored)."""
    pos, tri = P['pos'], P['tri']
    n = len(pos)
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for t in tri:
        r = [find(int(v)) for v in t]
        for q in r[1:]:
            if q != r[0]:
                parent[q] = r[0]
    root = np.array([find(int(v)) for v in tri[:, 0]])
    kind = np.zeros(len(tri), np.int16)
    info = []
    for r in np.unique(root):
        sel = root == r
        vs = np.unique(tri[sel])
        p = pos[vs]
        z0, z1 = p[:, 2].min(), p[:, 2].max()
        ax = np.abs(p[:, 0])
        w = ax.max() - ax.min()
        # her eye opening: z 1.232-1.258, |x| 0.020-0.056; brows ~z 1.274-1.280
        if z0 > 1.268:
            k = 'brow'
        elif z0 > 1.262 and w < 0.03:
            k = 'crease'
        elif z1 < 1.236:
            k = 'lower'
        elif ax.min() > 0.048 and w < 0.015:
            k = 'flick'
        elif w > 0.03 and z1 > 1.258:
            k = 'upper'
        elif w > 0.025:
            k = 'liner'
        else:
            k = 'other'
        kind[sel] = LASH_KIND.index(k)
        info.append((k, len(vs), *(round(float(q), 3) for q in (ax.min(), ax.max(), z0, z1))))
    return kind, info


SWATCH = {'skin': (SKIN, 1.0), 'white': ('#FFFFFF', 0.0), 'navy': (NAVY, 0.0)}   # 32 px cells, top right
LOWER_LINER = '#B48A8E'      # her liner runs on under the eye (part of the upper strip): Levi's soft lid line


def swatch_uv(name):
    k = list(SWATCH).index(name)
    return ((TEX - 32 * (k + 1) + 16) / TEX, 1.0 - 16 / TEX)


def bleed(rgba, cov, painted, n=3):
    """Grow a painted region n texels into texels no region painted (bilinear
    filtering at a UV island's edge then reads the region's own colour)."""
    cur = cov.copy()
    for _ in range(n):
        acc = np.zeros(rgba.shape)
        cnt = np.zeros(cov.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(cur, (dy, dx), (0, 1))
            val = np.roll(rgba, (dy, dx), (0, 1))
            acc += val * src[..., None]
            cnt += src
        grow = (cnt > 0) & ~cur & ~painted
        rgba[grow] = acc[grow] / cnt[grow][:, None]
        cur |= grow
    painted |= cur


def paint_atlas(tex, parts, kinds):
    """tex: (H, W, 3) float, rows top -> bottom. Returns (atlas, flushed atlas), RGBA float."""
    H, W = tex.shape[:2]
    rgba = np.ones((H, W, 4))
    rgba[..., :3] = tex
    rgba[..., 3] = 1.0
    painted = np.zeros((H, W), bool)
    face = parts['face']
    # face sheet: flat skin, shaded; Levi's marks painted from the 3D position
    cov, X, _ = raster(face['uv'], face['pos'][face['tri']] + ALIGN)
    sheet, Xsheet = cov, X
    rgba[sheet, :3] = hexrgb(SKIN)
    rgba[sheet, 3] = 1.0
    _levi_marks(rgba, sheet, X)
    # her rolled inner lip (a strip of the face with its own UVs, round the mouth
    # opening): Levi's lip line, darkest where it meets the cavity
    mouth = parts['mouth']
    mkey = {tuple(np.round(p / 1e-7).astype(np.int64)) for p in mouth['pos']}
    inner = np.array([tuple(np.round(p / 1e-7).astype(np.int64)) in mkey for p in face['pos']], float)
    fp = face['pos'][face['tri']]
    near = np.abs(fp[..., 0]).max(1) < 0.015
    near &= np.abs(fp[..., 2] - 1.202).max(1) < 0.008
    strip = near & (face['uv'][..., 1].max(1) < 0.236)
    cov, T, _ = raster(face['uv'][strip], inner[face['tri'][strip]][..., None])
    t = smooth(0.0, 0.55, T[..., 0])[..., None] * cov[..., None]
    rgba[..., :3] = rgba[..., :3] * (1 - t) + hexrgb(LIP_LINE) * t
    bleed(rgba, sheet, painted)
    # the mouth cavity and inner lips (口): the part gives them the palette's mouth
    # material; painted in its colour all the same
    P = parts['mouth']
    cov, _, _ = raster(P['uv'], np.zeros((len(P['tri']), 3, 1)))
    rgba[cov, :3] = hexrgb('#D88A86')
    rgba[cov, 3] = 1.0
    bleed(rgba, cov, painted)
    # white cup: white, the lid shadow hanging from the opening's upper edge (unshaded)
    P = parts['white']
    cov, X, _ = raster(P['uv'], P['pos'][P['tri']] + ALIGN)
    zup = _upper_rim(P)
    xa = np.abs(X[..., 0] - ALIGN[0])
    t = smooth(0.0, 0.0045, np.interp(xa, zup[:, 0], zup[:, 1]) - X[..., 2])
    col = hexrgb(LID_SHADE)[None, None] * (1 - t[..., None]) + np.ones(3) * t[..., None]
    rgba[cov, :3] = col[cov]
    rgba[cov, 3] = 0.0
    bleed(rgba, cov, painted)
    # iris
    _paint_iris(rgba, parts['iris'], painted)
    # lashes and brows: flat
    P = parts['lash']
    colour = {'upper': NAVY, 'liner': NAVY, 'flick': NAVY, 'lower': LOWER_LINER, 'brow': BROW,
              'crease': CREASE, 'other': NAVY}
    for k, hx in colour.items():
        sel = kinds == LASH_KIND.index(k)
        if not sel.any():
            continue
        cov, X, _ = raster(P['uv'][sel], P['pos'][P['tri'][sel]] + ALIGN)
        rgba[cov, :3] = hexrgb(hx)
        rgba[cov, 3] = 1.0 if k == 'crease' else 0.0
        xa = np.abs(X[..., 0] - ALIGN[0])
        if k == 'upper':      # the outer corner runs down to the lower lid: navy fades to the lid line
            low = (smooth(1.2945, 1.2905, X[..., 2]) * cov)[..., None]
            rgba[..., :3] = rgba[..., :3] * (1 - low) + hexrgb(LOWER_LINER) * low
        if k == 'lower':      # her lower liner: Levi's short lower lashes at the outer end only
            out = (smooth(0.041, 0.046, xa) * cov)[..., None]
            rgba[..., :3] = rgba[..., :3] * (1 - out) + hexrgb(LOW_LASH) * out
        bleed(rgba, cov, painted)
    # highlight (rebuilt by the part as one oval): white
    P = parts['hilite']
    cov, _, _ = raster(P['uv'], np.zeros((len(P['tri']), 3, 1)))
    rgba[cov, :3] = 1.0
    rgba[cov, 3] = 0.0
    bleed(rgba, cov, painted)
    for name, (hx, a) in SWATCH.items():
        k = list(SWATCH).index(name)
        rgba[0:32, TEX - 32 * (k + 1):TEX - 32 * k, :3] = hexrgb(hx)
        rgba[0:32, TEX - 32 * (k + 1):TEX - 32 * k, 3] = a
    flushed = rgba.copy()
    _flush_marks(flushed, sheet, Xsheet)
    return rgba, flushed


def _upper_rim(P):
    """(|x| from the midline, z) of the eye opening's upper edge (the white cup's
    rim, left eye), sampled along x."""
    from collections import Counter
    pos = P['pos'] + ALIGN
    E = Counter()
    for t in P['tri']:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            E[(min(a, b), max(a, b))] += 1
    rim = sorted({int(v) for e, c in E.items() if c == 1 for v in e})
    q = pos[rim]
    q = q[q[:, 0] > ALIGN[0]]
    xa = q[:, 0] - ALIGN[0]
    out = []
    for x in np.linspace(xa.min(), xa.max(), 40):
        near = q[np.abs(xa - x) < 0.0025]
        if len(near):
            out.append((x, near[:, 2].max()))
    return np.array(out)


def _flush_marks(rgba, sheet, X):
    """照れ: a deeper flush under the eyes and across the nose's sides with five
    clear hatch strokes (as round 10), fading out well inside the overlay patch
    the part cuts (FLUSH_BOX in levi/parts/_head_graft.py)."""
    x, z = X[..., 0] - ALIGN[0], X[..., 2]
    ax = np.abs(x)
    zc = 1.2485 + ALIGN[2] - 0.0185

    def paint(cov, hx):
        cov = np.clip(cov, 0, 1) * sheet
        rgba[..., :3] = rgba[..., :3] * (1 - cov[..., None]) + hexrgb(hx) * cov[..., None]
    fade = smooth(1.0, 0.75, np.hypot((ax - 0.036) / 0.021, (z - zc) / 0.0095))
    wash = np.exp(-(((ax - 0.036) / 0.016) ** 2 + ((z - zc) / 0.0058) ** 2))
    paint(0.62 * wash * fade, '#F49C98')
    for k in range(5):
        xs = 0.0265 + 0.0047 * k
        d = np.abs((ax - xs) + 0.5 * (z - zc)) - 0.0005
        inside = smooth(0.0035, 0.0025, np.abs(z - zc))
        paint(0.55 * smooth(0.0006, 0.0, d) * inside * fade, '#E07479')


def _levi_marks(rgba, sheet, X):
    """Levi's skin marks on the face sheet, by 3D position (aligned): a faint blush
    under the eyes, a small nose mark. (Lids, lashes, brows are geometry.)"""
    x, y, z = X[..., 0] - ALIGN[0], X[..., 1], X[..., 2]
    ax = np.abs(x)
    eye_z = 1.2485 + ALIGN[2]

    def paint(cov, hx):
        cov = np.clip(cov, 0, 1) * sheet
        rgba[..., :3] = rgba[..., :3] * (1 - cov[..., None]) + hexrgb(hx) * cov[..., None]
    blush = np.exp(-(((ax - 0.040) / 0.015) ** 2 + ((z - (eye_z - 0.0175)) / 0.0058) ** 2))
    paint(0.30 * blush, '#F6B6AE')
    for k in range(3):     # barely-there hatch strokes (as round 10)
        xs = 0.034 + 0.0047 * k
        d = np.abs((ax - xs) + 0.45 * (z - (eye_z - 0.0175))) - 0.0004
        paint(0.10 * smooth(0.0006, 0.0, d) * (np.abs(z - (eye_z - 0.0175)) < 0.002), '#EE9C98')
    # nose: a faint small mark at the tip
    nose = np.exp(-((ax / 0.0016) ** 2 + ((z - (eye_z - 0.0305)) / 0.0010) ** 2))
    paint(0.25 * nose, '#E2A49C')


def _paint_iris(rgba, P, painted):
    """Levi's iris on her iris tile: the dish's UVs are concentric rings round a
    centre; paint by the normalised UV radius / angle."""
    H, W = rgba.shape[:2]
    uv = P['uv'].reshape(-1, 2)
    tri_uv = P['uv']
    # both eyes share the tile: centre / radii from the outer ring
    c = 0.5 * (uv.min(0) + uv.max(0))
    r = 0.5 * (uv.max(0) - uv.min(0))
    cov, U, _ = raster(tri_uv, tri_uv)
    u = (U[..., 0] - c[0]) / r[0]
    v = (U[..., 1] - c[1]) / r[1]
    q = np.hypot(u, v)
    up = v                                         # +1 at the top of the iris (UV v up)
    col = hexrgb(IRIS_LO)[None, None] * np.ones((H, W, 1))
    # darker upper band, soft lower edge
    band = smooth(0.05, 0.35, up)[..., None]
    col = col * (1 - band) + hexrgb(IRIS_UP) * band
    # rounded darker pupil, a little above the centre, taller than wide
    pq = np.hypot(u / 0.30, (v - 0.12) / 0.48)
    pup = smooth(1.05, 0.9, pq)[..., None]
    col = col * (1 - pup) + hexrgb(PUPIL) * pup
    # navy rim
    rim = smooth(0.80, 0.90, q)[..., None]
    col = col * (1 - rim) + hexrgb(RIM) * rim
    rgba[cov, :3] = col[cov]
    rgba[cov, 3] = 0.0
    bleed(rgba, cov, painted)


def load_image(path):
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[::-1]            # rows top -> bottom
    bpy.data.images.remove(img)
    return px[..., :3].astype(float)


def save_png(path, rgba):
    import bpy
    h, w = rgba.shape[:2]
    img = bpy.data.images.new('head_atlas_out', w, h, alpha=True)
    img.colorspace_settings.name = 'sRGB'
    q = np.round(np.clip(rgba, 0, 1) * 255.0) / 255.0       # exact 8-bit values
    img.pixels.foreach_set(q[::-1].astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--pmx', required=True)
    ap.add_argument('--out', default=os.path.join(ROOT, 'assets', 'hyacine'))
    args = ap.parse_args(argv)
    m = pmxread.read(args.pmx)
    parts = extract(m)
    names, src, mo = morphs(m, parts)
    kinds, info = lash_kinds(parts['lash'])
    for row in info:
        print('LASH', row)
    bl = {b['name']: i for i, b in enumerate(m['bone_list'])}
    os.makedirs(args.out, exist_ok=True)
    data = {'parts': np.array(list(MATS)), 'morph_names': np.array(names), 'morph_src': np.array(src),
            'bone_names': np.array(BONES),
            'bone_head': np.array([our(m['bone_list'][bl[b]]['pos']) for b in BONES], np.float32),
            'lash_kind': np.array(LASH_KIND), 'lash_isl': kinds,
            'swatch_names': np.array(list(SWATCH)),
            'swatch_uv': np.array([swatch_uv(n) for n in SWATCH], np.float32)}
    for p, P in parts.items():
        data[p + '_pos'] = P['pos'].astype(np.float32)
        data[p + '_tri'] = P['tri'].astype(np.int32)
        data[p + '_uv'] = P['uv'].astype(np.float32)
        ptr, mvi, moff = mo[p]
        data[p + '_mptr'] = np.array(ptr, np.int64)
        data[p + '_mvi'] = np.array(mvi, np.int32)
        data[p + '_moff'] = np.array(moff, np.float32).reshape(-1, 3)
        print(f'PART {p:7s} verts {len(P["pos"]):5d} tris {len(P["tri"]):5d} morph offsets {len(mvi)}')
    meta = {'source': os.path.basename(args.pmx), 'frame': 'ours = MMD (x, z, y) * 0.08; winding reversed; uv v up',
            'texture': '颜.png -> head_atlas.png'}
    data['meta'] = np.array(json.dumps(meta, ensure_ascii=False))
    np.savez_compressed(os.path.join(args.out, 'head.npz'), **data)
    tex = load_image(os.path.join(os.path.dirname(args.pmx), '颜.png'))
    rgba, flushed = paint_atlas(tex, parts, kinds)
    save_png(os.path.join(args.out, 'head_atlas.png'), rgba)
    save_png(os.path.join(args.out, 'head_flush.png'), flushed)
    print('MORPHS', len(names), ' '.join(names))
    print('WROTE', args.out)


main()
