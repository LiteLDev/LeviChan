"""Petticoat: peach-pink gathered tiers below the skirt hem.

Objects:
  petticoat_core     low-res inner cone from the hips down; hidden by the skirt.
  petticoat_tier0-2  gathered ruffle tiers, outermost first. The two outer ones
                     show where the skirt's sides are lifted; the innermost
                     hangs lowest, beside the legs.

Each tier is one continuous band of gathered fabric, not a row of panels:
- Around the band the cloth hangs in broad rounded bell folds, unevenly
  spaced and unevenly deep (a cosine of a jittered phase), like the sheet's
  hanging bell flounces. Each tier has its own seed and phase, so the folds
  of neighbouring tiers do not line up.
- The hem is a row of rounded scallop petals, about three per bell, each a
  slight puff. A petal hangs lowest at its centre and meets the next in a
  small notch; the hem also rises in a soft arch over every bell fold.
- The folds are shallow at the top of a tier (where it is gathered into its
  seam, hidden under the tier or skirt above) and open up towards the hem;
  the band swells to a soft belly just above the hem.
- The hem turns under in a small rounded bead and returns a few px up
  inside, so the edge has thickness from any angle and the outline hull
  draws a line along every scallop.

The pink band's bottom outline is a bowl, lowest at the centre and rising
towards the sides (and higher at the back than the front in the side view).
It was measured on ref/{front,side,back}.png (panel rows, HEM_FRONT /
HEM_SIDE) instead of using the single spec.L['petticoat_hem_z'] landmark,
which only gives one height.

Rigging: the rig weights every skirt-family layer by angle x height to the
skirt chains, which follow the thighs (levi/rig.py). Every tier wraps round
both legs, well clear of them; none passes between the thighs.

Not modelled: the sheet's small shaded patch between the legs (front view,
~30 x 25 px under the skirt's centre front) and the pink sliver below the
back skirt's centre lobe. A layer hanging there would also hang in front of
the legs in the back view, where the sheet shows bare legs below the skirt,
and a layer between the thighs would need split leg weights.
"""
import bisect
import math

import bmesh
from mathutils import Vector

from levi import common, spec

L = spec.L
PX = 1.0 / spec.PX_PER_M

# ---------------------------------------------------------------- measured
# Bottom outline of the pink band (panel row) vs horizontal offset from the
# panel centre (px). Front and back views agree to ~2 px, and are symmetric.
HEM_FRONT = [(0, 629), (80, 626), (140, 620), (165, 613), (190, 607), (205, 600),
             (215, 594), (225, 587), (232, 580), (240, 568)]
# Side view: negative = character's front (-Y), positive = back (+Y).
HEM_SIDE = [(-170, 590), (-163, 600), (-155, 610), (-140, 617), (-120, 620),
            (-100, 625), (-60, 629), (0, 630), (40, 628), (70, 627), (90, 622),
            (105, 620), (120, 613), (135, 607), (145, 604), (155, 595),
            (162, 585), (170, 572)]
# Outer extent of the ruffles (px from centre) at the hem.
HALF_W = 235      # front view, +-X
FRONT_D = 163     # side view, -Y
BACK_D = 165      # side view, +Y

# ---------------------------------------------------------------- shape
DENSE = 1440      # samples of the dense hem outline (arc-length resampling)
JITTER = 0.35     # bell fold spacing irregularity (fraction of a bell)
DEPTH_VAR = 0.4   # bell depth / rise irregularity
PETALS_PER_BELL = 3
SPP = 6           # hem samples per petal (even: one sample sits on each notch)
PUFF = 1.6        # px a petal's centre puffs out past its notches
BELL_RISE = 0.6   # hem rise at a bell fold relative to the petal rise
BEAD = 2.0        # radius of the turned-under hem bead (px)

# Tiers, outermost first. The sheet's bottom outline is a bowl: the outer
# ruffles (lifted with the skirt's sides) end highest and the tiers further
# in hang lower.
#   name, hem outline (half width, front depth, back depth px, superellipse
#   exponent), lift (x0, x1), top, scallop petals, bell fold depth px,
#   petal rise px, seed
# top: ('free', height px, size of the top ring relative to the hem outline)
# for the outer tier, whose top is hidden under the skirt and over the core;
# ('core', px above the core's lower edge) for the inner tiers. These are not
# free-hanging rings: their tops are sewn onto the core cone (the inner the
# tier, the higher), so from below every tier reads as one continuous
# gathered panel nested inside the one around it.
# Lift: under the middle of the skirt, front and back, the sheet shows the
# legs from the skirt hem down, so within x0 px of the midline (front view)
# a tier's hem rises to LIFT_ROW, behind the skirt's centre hem, easing back
# to the measured bowl by x1.
TIERS = (
    ('petticoat_tier0', (HALF_W, FRONT_D, BACK_D, 2.0), (60, 80), ('free', 52, 0.80), 40, 12.0, 8.0, 1),
    ('petticoat_tier1', (0.77 * HALF_W, 0.77 * FRONT_D, 0.77 * BACK_D, 2.0), (60, 80), ('core', 14), 32, 10.0, 7.0, 2),
    ('petticoat_tier2', (144, 100, 100, 2.4), (60, 80), ('core', 30), 24, 8.0, 6.0, 3),
)
CORE_RX = L['waist_half_w'] * 1.40   # core top ring round the hips (m)
CORE_RY = 0.065
CORE_CY = L['waist_center_y'] * 0.6
LIFT_ROW = 585   # high enough that no lifted sliver peeks out under the skirt
# The lifted parts are hidden behind the skirt's long centre lobes, front and
# back; they are also drawn in towards the legs (by this fraction at the
# midline, easing out with the lift), so those lobes can hang down and tuck
# in instead of flaring out over the ruffles (which in the side view made
# them dangle past the outline as thin strips).
LIFT_PINCH = 0.25
# Rings from top to hem: (height between the hem (0) and the tier's top
# ring (1), size relative to the hem outline (None = the top ring, see
# TIERS: top), fold amount). The hem bead rings follow.
RINGS = (
    (1.00, None, 0.30),
    (0.30, 1.015, 1.00),
    (0.00, 1.00, 1.00),
)


def _interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return table[-1][1]


def _smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _hash(k, seed):
    """Deterministic pseudo-random number in [0, 1) for integer k."""
    v = math.sin(k * 12.9898 + seed * 78.233) * 43758.5453
    return v - math.floor(v)


def _dense_outline(shape):
    """Dense closed counter-clockwise hem outline (px) from the front centre.

    shape: (half width, front depth, back depth, exponent), a superellipse
    (exponent 2 = ellipse, larger = boxier).
    """
    w, fd, bd, ex = shape
    e = 2.0 / ex
    out = []
    for i in range(DENSE):
        phi = 2 * math.pi * i / DENSE - math.pi / 2
        c, s = math.cos(phi), math.sin(phi)
        out.append((w * math.copysign(abs(c) ** e, c), (fd if s < 0 else bd) * math.copysign(abs(s) ** e, s)))
    return out


def _outline(shape, n):
    """n points (px) evenly spaced by arc length on the hem outline from the
    front centre, with their outward unit normals."""
    pts = _dense_outline(shape)
    m = len(pts)
    cum = [0.0]
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % m]
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    res = []
    for i in range(n):
        s = (i / n * total) % total
        j = min(bisect.bisect_right(cum, s) - 1, m - 1)
        a, b = pts[j], pts[(j + 1) % m]
        t = (s - cum[j]) / max(cum[j + 1] - cum[j], 1e-9)
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1.0
        res.append(((a[0] + tx * t, a[1] + ty * t), (ty / ln, -tx / ln)))
    return res


def hem_z(x, y, lift=None):
    """World z of a tier's hem at the hem-outline point (x, y) (panel px).

    The hem point projects onto front-view column |x| and side-view column y.
    The measured bottom outline of each view is the lowest ruffle point over
    that column, so a hem point may hang no lower than either outline: take
    the higher of the two (the hem bead, BEAD px below this line, puts the
    petal crests a little below it, on the measured bottom row once their
    fold dips are averaged in). Inner tiers reach the lower centre of the
    bowl-shaped outline, outer tiers its lifted sides. lift = (x0, x1) raises
    the hem near the midline to LIFT_ROW (see TIERS).
    """
    ax = abs(x)
    row = min(_interp(HEM_FRONT, ax), _interp(HEM_SIDE, y))
    if lift and row > LIFT_ROW:
        row += (LIFT_ROW - row) * (1.0 - _smoothstep(lift[0], lift[1], ax))
    return spec.px_to_z(row)


class Waves:
    """Rounded, unevenly spaced waves around a band, s in [0, 1) (arc length)."""

    def __init__(self, count, seed, jitter, phase=0.0):
        self.n = count
        self.crest = [(k + 0.5 + phase + jitter * (_hash(k, seed) - 0.5)) / count for k in range(count)]
        self.amp = [1.0 + DEPTH_VAR * (2 * _hash(k, seed + 17) - 1) for k in range(count)]

    def __call__(self, s):
        """(f, amp): f in [0, 1) runs from one crest to the next (0.5 = the fold
        between them); amp eases between the two crests' depths."""
        c, n = self.crest, self.n
        s = (s - c[0]) % 1.0 + c[0]
        k = bisect.bisect_right(c, s) - 1
        b = c[(k + 1) % n] + (1.0 if k == n - 1 else 0.0)
        f = (s - c[k]) / (b - c[k])
        e = 0.5 - 0.5 * math.cos(math.pi * f)
        return f, self.amp[k] + (self.amp[(k + 1) % n] - self.amp[k]) * e


def _lift_pinch(x, lift):
    """Radial scale of the hem outline point at x px (see LIFT_PINCH)."""
    return 1.0 - LIFT_PINCH * (1.0 - _smoothstep(lift[0], lift[1], abs(x)))


def _core_bottom(phi):
    """(x, y, z) world point of the core's lower edge at ellipse angle phi."""
    _, dims0, lift0, (_, height0, top0) = TIERS[0][:4]
    c, s = math.cos(phi), math.sin(phi)
    hx, hy = dims0[0] * c, (dims0[1] if s < 0 else dims0[2]) * s
    # a few px below the outer tier's top edge so no gap shows
    z = hem_z(hx, hy, lift0) + (height0 - 8) * PX
    k = top0 * 0.97 * _lift_pinch(hx, lift0) * PX
    return Vector((k * hx, k * hy, z))


def _core_top(phi):
    """(x, y, z) world point of the core's top ring (round the hips) at angle phi."""
    return Vector((CORE_RX * math.cos(phi), CORE_CY + CORE_RY * math.sin(phi), L['hip_z']))


def _core_point(x, y, up_px):
    """Point on the core cone up_px above its lower edge, in the direction of
    the hem outline point (x, y) px."""
    w, fd, bd = TIERS[0][1][:3]
    phi = math.atan2(y / (fd if y < 0 else bd), x / w)
    b, t = _core_bottom(phi), _core_top(phi)
    return b.lerp(t, min(1.0, up_px * PX / (t.z - b.z)))


def _tier(col, idx, name, shape, lift, top, petals, depth_px, rise_px, seed):
    n = petals * SPP
    outline = _outline(shape, n)
    # hem heights (and the lift) from the outline point, then the pinch
    hems = [hem_z(p[0], p[1], lift) for p, _ in outline]
    hem = [((bx * k, by * k), nrm) for (bx, by), nrm in outline for k in (_lift_pinch(bx, lift),)]
    # petals are evenly spaced, SPP samples each, so every notch and every
    # petal centre falls on a sample; their depth varies per petal
    pamp = [1.0 + DEPTH_VAR * (2 * _hash(k, seed + 7) - 1) for k in range(petals)]
    bells = Waves(max(3, round(petals / PETALS_PER_BELL)), seed + 101, JITTER, phase=0.37 * idx)
    waves = []
    for i in range(n):
        s = i / n
        j = i + (SPP // 2) * (idx % 2)                  # neighbouring tiers: petals offset by half
        fp, ap = (j % SPP) / SPP, pamp[(j // SPP) % petals]
        fb, ab = bells(s)
        ub = 0.5 - 0.5 * math.cos(2 * math.pi * fb)      # 0 on a bell crest, 1 in the fold
        up = 0.5 - 0.5 * math.cos(2 * math.pi * fp)
        # petal: a round (circular-arc) bottom, small notch where two petals meet
        d = 2.0 * min(fp, 1.0 - fp)                       # 0 at the petal centre, 1 at the notch
        notch = 1.0 - math.sqrt(max(0.0, 1.0 - d * d))
        dip = depth_px * ab * ub + PUFF * up
        rise = rise_px * ap * notch + BELL_RISE * rise_px * ab * ub * ub
        waves.append((dip, rise))
    # top ring: free (above the hem, scaled) or sewn onto the core
    if top[0] == 'free':
        tops = [Vector((top[2] * bx * PX, top[2] * by * PX, hems[i] + top[1] * PX))
                for i, ((bx, by), _) in enumerate(hem)]
    else:
        tops = [_core_point(bx, by, top[1]) for (bx, by), _ in hem]
    loops = []
    for h, scale, amount in RINGS:
        loop = []
        for i, ((bx, by), (nx, ny)) in enumerate(hem):
            dip, rise = waves[i]
            d = dip * amount * PX
            if scale is None:                            # the top ring
                p = tops[i]
                loop.append(Vector((p.x - nx * d, p.y - ny * d, p.z)))
                continue
            z = hems[i] + h * (tops[i].z - hems[i]) + rise * PX * (1.0 - h)
            loop.append(Vector((scale * bx * PX - nx * d, scale * by * PX - ny * d, z)))
        loops.append(loop)
    # hem bead: turn under and return inside
    edge = loops[-1]
    for dz, din in ((-BEAD, BEAD), (BEAD * 1.2, 2.2 * BEAD)):
        loop = []
        for i, ((bx, by), (nx, ny)) in enumerate(hem):
            p = edge[i]
            loop.append(Vector((p.x - nx * din * PX, p.y - ny * din * PX, p.z + dz * PX)))
        loops.append(loop)
    return _finish(col, common.toon_material('petticoat'), name, loops)


def _finish(col, mat, name, loops):
    """Loft the rings into a sheet object with an outline.

    recalc_face_normals is ambiguous on an open tube, so orientation is set
    explicitly: faces point OUTWARD (away from the body axis), so the outline
    hull sits on the outside of the hem bead and draws a line along every
    scallop; the hull's backface culling keeps it off the fill.
    """
    bm = common.loft(loops, closed=True)
    out = sum(f.normal.dot(Vector((c.x, c.y, 0.0))) * f.calc_area()
              for f in bm.faces for c in (f.calc_center_median(),))
    if out < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    obj = common.new_object(col, name, bm, [mat])
    common.shade_smooth(obj, 70.0)
    common.add_outline(obj)
    return obj


def _core(col, mat):
    """Hidden inner cone from the hips down into the top of the outer tier."""
    n = 32
    top = [_core_top(2 * math.pi * i / n) for i in range(n)]
    bot = [_core_bottom(2 * math.pi * i / n) for i in range(n)]
    return _finish(col, mat, 'petticoat_core', [top, bot])


def build(col):
    _core(col, common.toon_material('petticoat'))
    for idx, tier in enumerate(TIERS):
        _tier(col, idx, *tier)
