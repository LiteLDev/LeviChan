"""Corset bodice: strapless white bodice with sweetheart neckline, princess
seams, front lacing with eyelets and a dark-green diamond, a leaf cluster at
the neckline (character's left), and the green waist bow whose two pairs of
thin ribbon tails ripple down the front of the skirt.

All shapes are fitted to ref/front.png and ref/side.png (panel pixels, measured
around this part's own region; see the tables below). Front-view columns are
measured relative to FRONT_CX: the drawn bodice is centred ~1.3 px right of the
panel centre, so features are kept symmetric about x = 0 using offsets from the
drawn centre instead of absolute columns.
"""
import math

import bisect

import bmesh
import bpy
from mathutils import Vector

from levi import common, spec
from levi.parts import skirt

PX = spec.px_to_h(1.0)    # one panel pixel in metres
FRONT_CX = 321.0          # drawn centre line of the bodice in ref/front.png


def Z(row):
    return spec.px_to_z(row)


def interp(table, t):
    """Piecewise-linear lookup in a sorted [(t, value), ...] table (clamped)."""
    if t <= table[0][0]:
        return table[0][1]
    for (t0, v0), (t1, v1) in zip(table, table[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return table[-1][1]


def smooth_interp(table, t):
    """C1 cubic Hermite through a sorted [(t, value), ...] table (clamped).

    Tangents are finite differences over the real knot spacing, so unevenly
    spaced knots give no slope jumps.
    """
    ts = [a for a, _ in table]
    vs = [b for _, b in table]
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    i = min(bisect.bisect_right(ts, t) - 1, len(ts) - 2)

    def slope(k):
        a, b = max(k - 1, 0), min(k + 1, len(ts) - 1)
        return (vs[b] - vs[a]) / (ts[b] - ts[a])

    h = ts[i + 1] - ts[i]
    u = (t - ts[i]) / h
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return h00 * vs[i] + h10 * h * slope(i) + h01 * vs[i + 1] + h11 * h * slope(i + 1)


def catmull_path(pts, k):
    """Catmull-Rom spline through Vector control points, k samples per span."""
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        for s in range(k):
            u = s / k
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * (u * u)
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * (u ** 3)))
    out.append(pts[-1].copy())
    return out


# ---------------------------------------------------------------- measurements
# Bodice profile per sheet row: (half-width from front view, front-most y and
# back-most y from side view), all in panel px. The back is hidden by hair in
# both side and back views, so its depth is a plausible guess.
PROFILE = [
    # row, half_w, y_front, y_back
    # half_w is the drawn line centre minus half the outline; y_front allows for
    # the full ~1.4 px outline hull (side silhouette).
    (230, 55.5, -84.0, 9.0),
    (240, 57.0, -87.0, 8.0),
    (250, 57.0, -91.5, 8.0),
    (260, 56.5, -94.0, 6.0),
    (270, 54.8, -93.5, 3.0),
    (280, 51.0, -90.5, 0.0),
    (290, 49.3, -88.5, -4.0),
    (300, 47.0, -87.5, -8.0),
    (310, 45.0, -86.8, -11.0),
    (320, 45.0, -86.6, -13.0),
    (330, 46.5, -86.6, -13.0),
    (340, 48.0, -86.6, -12.0),
    (352, 51.0, -87.0, -10.0),
]
ROW_BOT = 352             # hidden under the skirt waistband
SUPER_P = 2.3             # superellipse exponent: slightly flattened corset front

# Sweetheart neckline: top row vs |x| / half_w across the front half.
NECK_FRONT = [(0.0, 243.0), (0.10, 241.5), (0.28, 237.0), (0.50, 234.0),
              (0.62, 233.5), (0.80, 235.5), (1.0, 240.0)]
NECK_BACK_DROP = 8.0      # px lower at the centre back than at the side seam

# Princess seams: |x| offset (px from centre) per row.
SEAM = [(236, 36.5), (250, 36.5), (266, 36.0), (278, 30.5), (290, 24.5), (300, 21.5),
        (320, 20.0), (348, 19.0)]

# Lacing.
DIAMOND = (290.0, 10.5, 6.0)                 # centre row, half-width, half-height
EYELET_ROWS = [295.5, 303.5, 311.5, 319.5]
EYELET_DX = 24.5
LACE_END = (334.0, 4.0)                      # row, |dx| where the lacing meets the knot

# Bow (front view, px; centre knot + two hollow loops).
KNOT = (321.0, 338.0)
BOW_LOOP_L = [(318, 340), (306, 332), (293, 327.5), (289, 333), (289.5, 344), (292, 354.5),
              (305, 349), (317, 343), (321, 339)]
BOW_Y_KNOT = -97.0        # side view: bow front edge at col ~220 incl. outline
BOW_Y_SLOPE = 0.62        # loops sweep back around the waist

# Ribbon tails (front view, px). Two thin strands per side meet at the tip.
TAILS = {
    'L_wave': ([(320, 342), (310, 387), (286, 420), (273, 440), (298, 468), (303, 480),
                (300, 490), (289, 498), (276, 518), (281, 533), (292, 550), (293, 558)], 3.2),
    'L_thin': ([(320, 344), (316, 362), (307, 420), (300, 466), (291, 497), (291, 532),
                (292, 557)], 1.7),
    'R_wave': ([(323, 342), (341, 381), (358, 420), (371, 441), (346, 466), (340, 486),
                (356, 500), (369, 520), (360, 537), (350, 558)], 3.2),
    'R_thin': ([(323, 344), (328, 362), (335, 420), (348, 470), (358, 500), (354, 532),
                (349, 557)], 1.7),
}
# Tails sit TAIL_PROUD px in front of the skirt's cloth surface, taken from
# levi.parts.skirt.front_surface_y() (its godet folds included; tail x is
# world x, the same frame the skirt uses). Fallback only where the skirt does
# not reach a tail point: the measured envelope below - side-view front edge
# (px from centre, side_mask) and front-view half width.
SKIRT_FRONT = [(340, -92), (360, -98), (380, -106), (400, -110), (420, -111), (440, -115),
               (460, -122), (480, -131), (500, -140.5), (520, -151.5), (540, -161.5),
               (560, -170.5), (580, -176)]
SKIRT_HW = [(340, 50), (400, 100), (450, 140), (500, 180), (560, 230)]
TAIL_PROUD = 2.5

# Leaf cluster at the neckline, character's left (image right in front view).
# (base col,row) -> (tip col,row), half-width px, forward tilt px.
LEAVES = [
    ((356.0, 248.5), (342.5, 230.0), 5.0, -1.0),
    ((359.5, 249.0), (361.5, 227.5), 6.5, 0.0),
    ((362.0, 249.5), (378.5, 243.0), 5.0, -1.0),
]

OUTLINE_FINE = 0.0007     # line weight for thin trims (seams, lacing, ribbons)


# ---------------------------------------------------------------- bodice shape
_HW_T = [(r, w) for r, w, _, _ in PROFILE]
_YF_T = [(r, f) for r, _, f, _ in PROFILE]
_YB_T = [(r, b) for r, _, _, b in PROFILE]


def profile(row):
    """(half_w, y_front, y_back) in metres at a sheet row."""
    return (smooth_interp(_HW_T, row) * PX, smooth_interp(_YF_T, row) * PX,
            smooth_interp(_YB_T, row) * PX)


def _sp(v, e):
    return math.copysign(abs(v) ** e, v)


def section_point(theta, row):
    hw, yf, yb = profile(row)
    yc, d = (yf + yb) / 2, (yb - yf) / 2
    e = 2.0 / SUPER_P
    return Vector((hw * _sp(math.cos(theta), e), yc + d * _sp(math.sin(theta), e), Z(row)))


def front_y(x, row):
    """Front surface y of the bodice at world x and sheet row."""
    hw, yf, yb = profile(row)
    yc, d = (yf + yb) / 2, (yb - yf) / 2
    t = min(abs(x) / hw, 0.999)
    return yc - d * (1 - t ** SUPER_P) ** (1 / SUPER_P)


def neck_row(theta):
    s, c = math.sin(theta), math.cos(theta)
    if s <= 0:   # front half
        xn = _sp(abs(c), 2.0 / SUPER_P)
        return smooth_interp(NECK_FRONT, xn)
    return NECK_FRONT[-1][1] + NECK_BACK_DROP * s


NU = 48                   # shell segments around (front centre is a vertex)


def build_shell(col, mat):
    nu, nv = NU, 20
    bm = bmesh.new()
    grid = []
    for j in range(nv + 1):
        v = j / nv
        ring = []
        for i in range(nu):
            th = -math.pi / 2 + 2 * math.pi * i / nu
            top = neck_row(th)
            # denser rows near the neckline where the shape changes most
            vv = 1 - (1 - v) ** 1.25
            row = ROW_BOT + (top - ROW_BOT) * vv
            ring.append(bm.verts.new(section_point(th, row)))
        grid.append(ring)
    for j in range(nv):
        a, b = grid[j], grid[j + 1]
        for i in range(nu):
            k = (i + 1) % nu
            # theta increases counter-clockwise seen from +Z, rows go up:
            # (a_i, a_k, b_k, b_i) faces outward.
            bm.faces.new((a[i], a[k], b[k], b[i]))
    obj = common.new_object(col, 'bodice_shell', bm, [mat])
    common.shade_smooth(obj, 60)
    common.add_outline(obj)
    return obj


def outward(theta, row):
    """Horizontal outward normal of the shell's superellipse section."""
    hw, yf, yb = profile(row)
    d = (yb - yf) / 2
    c, s = math.cos(theta), math.sin(theta)
    q = SUPER_P - 1
    # gradient of |x/hw|^p + |y/d|^p, written in the section's angle parameter
    gx = _sp(c, 2.0 * q / SUPER_P) / hw
    gy = _sp(s, 2.0 * q / SUPER_P) / d
    return Vector((gx, gy, 0)).normalized()


def build_piping(col, mat):
    """Bound neckline edge: gives the open top of the shell its drawn line."""
    pts, dirs = [], []
    for i in range(NU):
        th = -math.pi / 2 + 2 * math.pi * i / NU
        row = neck_row(th) + 0.6
        o = outward(th, row)
        pts.append(section_point(th, row) + o * 0.0004)
        dirs.append(o)
    bm = band(pts, 0.0024, 0.0016, loop=True, faces=dirs)
    return finish(col, 'bodice_piping', [bm], mat, outline=spec.OUTLINE_WIDTH * 0.8)


# ---------------------------------------------------------------- trims
def band(points, width, thick, face=Vector((0, -1, 0)), widths=None, loop=False, faces=None):
    """Closed (capped) rectangular-section strip along `points`.

    `face` is the direction the strip's flat side looks toward; `width` lies in
    the plane perpendicular to it. widths: optional per-point width scale.
    loop: the path is a closed loop (no caps). faces: optional per-point face
    direction overriding `face`.
    """
    pts = [Vector(p) for p in points]
    n_pts = len(pts)
    rings = []
    for i, p in enumerate(pts):
        if loop:
            t = (pts[(i + 1) % n_pts] - pts[i - 1]).normalized()
        else:
            t = (pts[min(i + 1, n_pts - 1)] - pts[max(i - 1, 0)]).normalized()
        f = faces[i] if faces else face
        b = f - t * f.dot(t)
        if b.length < 1e-6:
            b = t.orthogonal()
        b.normalize()
        n = t.cross(b).normalized()
        w = width * (widths[i] if widths else 1.0) / 2
        h = thick / 2
        rings.append([p + n * w + b * h, p - n * w + b * h, p - n * w - b * h, p + n * w - b * h])
    if not loop:
        return common.loft(rings, closed=True, cap_start=True, cap_end=True)
    bm = common.loft(rings + [rings[0]], closed=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def merge_bms(bms):
    out = bmesh.new()
    for bm in bms:
        me_tmp = bpy.data.meshes.new('_tmp_bodice')
        bm.to_mesh(me_tmp)
        bm.free()
        out.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)
    return out


def finish(col, name, bms, mat, smooth=True, outline=OUTLINE_FINE):
    obj = common.new_object(col, name, merge_bms(bms), [mat])
    if smooth:
        common.shade_smooth(obj, 50)
    common.add_outline(obj, width=outline)
    return obj


def on_shell(dx_px, row, lift_px):
    """Point on the bodice front surface (front-view dx px from centre)."""
    x = dx_px * PX
    return Vector((x, front_y(x, row) - lift_px * PX, Z(row)))


def shell_path(a, b, n, lift_px):
    """Sample a straight front-view line (dx,row)->(dx,row) projected onto the shell."""
    return [on_shell(a[0] + (b[0] - a[0]) * s / n, a[1] + (b[1] - a[1]) * s / n, lift_px)
            for s in range(n + 1)]


def build_seams(col, mat):
    bms = []
    for sx in (-1, 1):
        rows = [236 + (348 - 236) * s / 18 for s in range(19)]
        pts = [on_shell(sx * smooth_interp(SEAM, r), r, 0.35) for r in rows]
        # start just under the neckline at this offset
        pts[0] = on_shell(sx * SEAM[0][1], neck_row_at_dx(SEAM[0][1]) + 1.5, 0.35)
        bms.append(band(pts, 0.0011, 0.0009))
    return finish(col, 'bodice_seams', bms, mat, outline=0.0010)


def neck_row_at_dx(dx_px):
    """Neckline row at a front-view offset, consistent with neck_row(theta):
    the shell normalises x by the half width at the neckline row itself."""
    row = NECK_FRONT[0][1]
    for _ in range(4):
        hw = profile(row)[0] / PX
        row = smooth_interp(NECK_FRONT, min(dx_px / hw, 1.0))
    return row


def build_lacing(col, mat_green):
    bms = []
    # criss-cross between the eyelet columns
    rows = EYELET_ROWS
    for i in range(len(rows) - 1):
        for sx in (-1, 1):
            # alternate which strand lies on top so the crossings never coincide
            lift = 1.0 if (sx > 0) == (i % 2 == 0) else 1.7
            bms.append(band(shell_path((sx * EYELET_DX, rows[i]), (-sx * EYELET_DX, rows[i + 1]), 4, lift),
                            0.0021, 0.0010))
    # top V from the diamond's lower tip out to the first eyelets
    dr, dw, dh = DIAMOND
    for sx in (-1, 1):
        bms.append(band(shell_path((0, dr + dh), (sx * EYELET_DX, rows[0]), 3, 1.0), 0.0021, 0.0010))
        # last eyelets down into the bow knot
        bms.append(band(shell_path((sx * EYELET_DX, rows[-1]), (sx * LACE_END[1], LACE_END[0]), 4, 1.0),
                        0.0021, 0.0010))
    # eyelets: small studs at the ends of every lacing row
    for r in rows:
        for sx in (-1, 1):
            c = on_shell(sx * (EYELET_DX + 0.8), r, 1.2)
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=1.6 * PX)
            bmesh.ops.scale(bm, vec=(1.0, 0.6, 1.0), verts=bm.verts)
            bmesh.ops.translate(bm, vec=c, verts=bm.verts)
            bms.append(bm)
    return finish(col, 'bodice_lacing', bms, mat_green)


def build_diamond(col, mat):
    dr, dw, dh = DIAMOND
    bm = bmesh.new()
    # 3x3 grid in diamond (u,v) space, conforming to the shell
    vs = {}
    for a in range(3):
        for b in range(3):
            u, v = a - 1, b - 1                    # -1..1
            dx = (u - v) * 0.5 * dw
            row = dr + (u + v) * 0.5 * dh
            vs[a, b] = bm.verts.new(on_shell(dx, row, 1.0))
    for a in range(2):
        for b in range(2):
            bm.faces.new((vs[a, b], vs[a + 1, b], vs[a + 1, b + 1], vs[a, b + 1]))
    sol = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [e for e in sol['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0.0008, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(col, 'bodice_diamond', [bm], mat, smooth=False, outline=0.0009)


def bow_y(dx_px, row):
    """Bow depth: knot forward, loops wrapping back but kept off the shell."""
    y = (BOW_Y_KNOT + BOW_Y_SLOPE * abs(dx_px)) * PX
    return min(y, front_y(dx_px * PX, min(row, ROW_BOT)) - 2.5 * PX)


def build_bow(col, mat):
    bms = []
    for sx in (-1, 1):
        ctrl = [Vector((sx * (c - FRONT_CX), 0, r)) for c, r in BOW_LOOP_L]
        path = catmull_path(ctrl, 3)
        pts = [Vector((p.x * PX, bow_y(p.x, p.z), Z(p.z))) for p in path]
        bms.append(band(pts, 3.6 * PX, 0.0016))
    # knot
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=1.0)
    bmesh.ops.scale(bm, vec=(5.0 * PX, 3.0 * PX, 5.5 * PX), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((KNOT[0] - FRONT_CX) * PX, (BOW_Y_KNOT + 1.0) * PX, Z(KNOT[1])),
                        verts=bm.verts)
    bms.append(bm)
    return finish(col, 'bodice_bow', bms, mat, outline=0.0011)


def skirt_surface_y(dx_px, row):
    # the skirt's own cloth surface (with its godet folds) where it exists;
    # the measured envelope above its waist ring
    y = skirt.front_surface_y(dx_px, row)
    if y is not None:
        return y
    front = interp(SKIRT_FRONT, row)
    hw = interp(SKIRT_HW, row)
    t = min(abs(dx_px) / hw, 0.95)
    return front * math.sqrt(1 - t * t)


def build_tails(col, mat):
    bms = []
    for name, (ctrl, width_px) in TAILS.items():
        cpts = [Vector((c - FRONT_CX, 0, r)) for c, r in ctrl]
        path = catmull_path(cpts, 2)
        pts = []
        for p in path:
            dx, row = p.x, p.z
            # most forward skirt point under the ribbon's width, so a ribbon
            # crossing a godet fold bridges it instead of sinking into it
            half = 0.5 * width_px + 1.0
            y = min(skirt_surface_y(dx + o, row) for o in (-half, 0.0, half)) - TAIL_PROUD
            # near the knot the tails leave the bow, in front of the skirt top
            k = max(0.0, min(1.0, (372 - row) / 30))
            y = y * (1 - k) + min(y, BOW_Y_KNOT + 1.0) * k
            pts.append(Vector((dx * PX, y * PX, Z(row))))
        n = len(pts)
        widths = [1.0 if i < n - 3 else 0.85 for i in range(n)]
        bms.append(band(pts, width_px * PX, 0.0011, widths=widths))
    return finish(col, 'bodice_ribbon_tails', bms, mat, outline=OUTLINE_FINE)


# ---------------------------------------------------------------- leaves
def leaf_bm(base, tip, half_w, tilt_px):
    """Pointed leaf with a folded midrib; base/tip are front-view (col,row)."""
    b = Vector((base[0] - FRONT_CX, 0, base[1]))
    t = Vector((tip[0] - FRONT_CX, 0, tip[1]))
    axis = t - b
    side = Vector((-axis.z, 0, axis.x)).normalized()
    bm = bmesh.new()
    stations = 6
    rows = []
    for s in range(stations + 1):
        u = s / stations
        c = b + axis * u
        # narrow stalk at the base (never zero width: no degenerate faces)
        w = half_w * max(math.sin(math.pi * min(1.0, u * 1.05)) ** 0.8, 0.15)
        pts = [c - side * w, c, c + side * w]
        # lie on the curved bodice surface (so the leaves read in the side view
        # too), tips lifting by tilt_px; the midrib stands proud as a fold.
        # Depth is sampled no further out than 90 % of the half width: past the
        # shell's side the surface turns backward and would curl the tip.
        ys = [front_y(math.copysign(min(abs(q.x) * PX, 0.9 * profile(q.z)[0]), q.x), q.z) / PX
              - 1.5 - tilt_px * u - (1.2 if k == 1 else 0.0)
              for k, q in enumerate(pts)]
        rows.append([Vector((q.x * PX, yy * PX, Z(q.z))) for q, yy in zip(pts, ys)])
    vs = [[bm.verts.new(p) for p in r] for r in rows[:-1]]
    tip_v = bm.verts.new(rows[-1][1])
    for s in range(stations - 1):
        for j in range(2):
            bm.faces.new((vs[s][j], vs[s][j + 1], vs[s + 1][j + 1], vs[s + 1][j]))
    for j in range(2):
        bm.faces.new((vs[-1][j], vs[-1][j + 1], tip_v))
    # give the leaf a little thickness so the outline hull reads cleanly
    ext = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    moved = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0.0009, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def build_leaves(col, mat):
    bms = [leaf_bm(*lf) for lf in LEAVES]
    return finish(col, 'bodice_leaves', bms, mat, smooth=False, outline=0.0012)


# ---------------------------------------------------------------- entry
def build(col):
    dress = common.toon_material('dress')
    green = common.toon_material('green')
    leaf = common.toon_material('leaf')
    build_shell(col, dress)
    build_piping(col, dress)
    build_seams(col, dress)
    build_diamond(col, green)
    build_lacing(col, green)
    build_bow(col, green)
    build_tails(col, green)
    build_leaves(col, leaf)
    return col
