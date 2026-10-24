"""Skin body: neck, torso, A-pose arms with five-fingered hands, legs, feet.

Everything is a swept ring loft (quads, with small triangle fans only at
rounded tips), so each limb carries clean edge loops at the shoulder, elbow,
wrist, hip, knee and ankle. The head is a separate part; the neck stops in a
tilted ring tucked just under the jaw (spec.L['chin_z']).

All shape data below is in *panel pixels* measured on ref/{front,side}.png
(see `P()`): x = offset from the panel centre column (+ = character's left),
y = side-view offset (- = forward), row = image row (ground at
spec.SHEET_GROUND_Y). The exposed skin (neck, shoulders, upper chest, hands,
legs below the petticoat) was fitted to the reference silhouette; the parts
hidden under the bodice / sleeves / skirt / shoes are kept a few pixels inside
the clothing outline so the clothing parts can wrap them.

Local corrections vs. spec.L (re-measured on the reference):
  * knee at row ~700 (spec says 740): the leg is widest there in both views.
  * shoulder joint / elbow / wrist moved to fit the visible upper arm and the
    hands (wrist ~(220, 438) px instead of (200, 455)).
  * neck centre y = -31 px (spec -38).
"""
import math

import bmesh
from mathutils import Matrix, Vector

from .. import common, spec

MARGIN = 1.0  # px pulled in so the outline hull lands on the reference line


def P(x, y, row):
    """Panel pixels -> world metres."""
    return Vector((spec.px_to_h(x), spec.px_to_h(y), spec.px_to_z(row)))


px = spec.px_to_h  # panel pixels -> metres


# ---------------------------------------------------------------- sweep
def _frames(centers, side_hints, tangent=None):
    n = len(centers)
    out = []
    for i in range(n):
        if tangent is not None:
            t = Vector(tangent).normalized()
        else:
            a = centers[max(i - 1, 0)]
            b = centers[min(i + 1, n - 1)]
            t = (b - a).normalized()
        h = side_hints[i]
        side = (h - t * h.dot(t)).normalized()
        up = t.cross(side)
        out.append((t, side, up))
    return out


def _ring_dir(theta, p):
    c, s = math.cos(theta), math.sin(theta)
    e = 2.0 / p
    return (math.copysign(abs(c) ** e, c), math.copysign(abs(s) ** e, s))


def sweep(bm, centers, side_hints, radii, n, p=2.0, cap0='pole', cap1='pole',
          cap0_len=0.0, cap1_len=0.0, ring_fn=None, tangent=None):
    """Loft rings along `centers` into `bm`.

    radii[i] = (side+, side-, up+, up-) in metres; side = hint orthogonalised
    against the tangent, up = tangent x side. p: superellipse exponent (scalar
    or per-ring list). cap: 'pole' (triangle fan to a tip point offset by
    cap_len along the tangent), 'ngon' or None. ring_fn(i, co) may move ring
    vertices after placement. tangent: fixed ring normal for all rings (for
    tables measured as horizontal / vertical slices); default follows the
    centre line. Returns the list of vertex rings.
    """
    frames = _frames(centers, side_hints, tangent)
    rings = []
    for i, (c, (t, side, up), r) in enumerate(zip(centers, frames, radii)):
        pi = p[i] if isinstance(p, (list, tuple)) else p
        ring = []
        for k in range(n):
            dx, dy = _ring_dir(2 * math.pi * k / n, pi)
            rs = r[0] if dx >= 0 else r[1]
            ru = r[2] if dy >= 0 else r[3]
            co = c + side * (dx * rs) + up * (dy * ru)
            if ring_fn:
                co = ring_fn(i, co)
            ring.append(bm.verts.new(co))
        rings.append(ring)
    faces = []
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            faces.append(bm.faces.new((a[k], a[j], b[j], b[k])))
    for ring, cap, ln, (t, _, _), c in ((rings[0], cap0, -cap0_len, frames[0], centers[0]),
                                        (rings[-1], cap1, cap1_len, frames[-1], centers[-1])):
        if cap == 'ngon':
            faces.append(bm.faces.new(ring))
        elif cap == 'pole':
            tip = bm.verts.new(sum((v.co for v in ring), Vector()) / n + t * ln)
            for k in range(n):
                faces.append(bm.faces.new((ring[k], ring[(k + 1) % n], tip)))
    return rings


# ---------------------------------------------------------------- torso + neck
# row, half width, front y, back y, superellipse exponent  (panel px)
TORSO = [
    (148, 12.5, -42, -17, 2.0),   # tucked inside the head (tilted, see below)
    (161, 13.5, -44, -17, 2.0),   # chin_z: seam under the jaw
    (170, 13.5, -44, -17, 2.0),
    (176, 14.0, -45, -16, 2.0),
    (180, 14.6, -45, -15, 2.0),
    (183, 17.0, -45, -14, 2.0),   # neck base
    (185.5, 23.0, -45, -12.5, 2.1),
    (188, 34.0, -45, -11, 2.2),
    (191, 47.0, -45, -9, 2.4),
    (194, 58.0, -45, -7, 2.5),
    (197, 66.0, -45, -5.5, 2.6),
    (201, 72.0, -46, -4, 2.7),
    (205, 74.5, -48, -2, 2.7),    # shoulder line
    (210, 75.0, -51, -1, 2.6),
    (216, 73.5, -54, -1, 2.5),
    (222, 72.0, -57, -1, 2.4),
    (230, 65.0, -61, 0, 2.3),
    (240, 56.0, -66, 0, 2.2),     # bodice top / armpit
    (250, 54.0, -76, 2, 2.2),
    (262, 53.0, -85, 5, 2.2),     # bust (under the bodice)
    (275, 51.0, -84, 6, 2.2),
    (290, 46.0, -78, 5, 2.2),
    (305, 42.0, -76, 2, 2.2),
    (320, 39.0, -76, -1, 2.2),
    (335, 39.0, -76, -2, 2.2),    # waist
    (350, 42.0, -74, 0, 2.2),
    (370, 48.0, -70, 6, 2.2),
    (395, 55.0, -66, 14, 2.3),
    (420, 60.0, -60, 19, 2.3),
    (445, 62.0, -52, 19, 2.3),    # hips
    (465, 57.0, -42, 13, 2.2),
    (480, 42.0, -32, 4, 2.0),
    (489, 22.0, -24, -4, 2.0),
]
NECK_TILT = 0.6  # the neck-top rings rise toward the back to hide behind the jaw
NECK_SEAM_ROW = 161  # rings at/above this row (spec chin_z) get the tilt


def build_torso(bm):
    centers, hints, radii, ps = [], [], [], []
    for row, hw, yf, yb, p in TORSO:
        yc = (yf + yb) / 2
        centers.append(P(0, yc, row))
        hints.append(Vector((1, 0, 0)))
        ry = (yb - yf) / 2
        radii.append((px(hw), px(hw), px(ry), px(ry)))
        ps.append(p)
    # Rings are horizontal slices (the table rows); t=-Z, side=+X -> up=-Y.

    def tilt(i, co):
        if TORSO[i][0] <= NECK_SEAM_ROW:
            co = co.copy()
            co.z += max(0.0, co.y - px(TORSO[i][2])) * NECK_TILT
        return co

    sweep(bm, centers, hints, radii, n=28, p=ps, cap0='ngon', cap1='pole',
          cap1_len=px(4), ring_fn=tilt, tangent=(0, 0, -1))


# ---------------------------------------------------------------- arms + hands
# Left arm (+X); the right arm is the mirror image.
SHOULDER = (66, -27, 214)
ELBOW = (118, -18, 352)
WRIST = (220, -24, 438)
HAND_DIR = (60, 4, 42)       # wrist -> middle fingertip (x, y, rows down)
HAND_W_FRONT = 0.675         # share of the palm width seen in the front view


def hand_frame():
    """Unit vectors (d: along the hand, w: toward the thumb, n: palm normal)."""
    d = Vector((HAND_DIR[0], HAND_DIR[1], -HAND_DIR[2])).normalized()
    perp_up = Vector((-d.z, 0, d.x)).normalized()      # in the front plane, upward
    w = (perp_up * HAND_W_FRONT + Vector((0, -1, 0)) * math.sqrt(1 - HAND_W_FRONT ** 2))
    w = (w - d * w.dot(d)).normalized()
    n = d.cross(w)   # palm side for the left hand
    return d, w, n


def build_arm(bm):
    S, E, W = P(*SHOULDER), P(*ELBOW), P(*WRIST)
    u = (E - S).normalized()
    f = (W - E).normalized()
    d, w, n = hand_frame()

    def front_side(t):
        return Vector((-t.z, 0, t.x)).normalized()  # outward/up in front plane

    k = px(1)
    secs = [  # (centre, side hint or hand-twist weight 0..1, (side+, side-, front, back) px)
        (S - u * 13 * k, front_side(u), (6, 7, 8, 8)),
        (S - u * 9 * k, front_side(u), (10, 11.5, 13.5, 13.5)),
        (S - u * 4 * k, front_side(u), (12.5, 14.5, 17, 17)),
        (S, front_side(u), (13.5, 15.5, 18.5, 18)),
        (S + u * 15 * k, front_side(u), (13.5, 15.0, 18, 17)),
        (S + u * 35 * k, front_side(u), (13.5, 14.5, 16, 15.5)),
        (S + u * 62 * k, front_side(u), (13.5, 13.5, 14.5, 14)),
        (S + u * 92 * k, front_side(u), (13.0, 12.5, 13, 13)),
        (E - u * 14 * k, front_side(u), (12.5, 12.0, 12.5, 12.5)),
        (E, front_side((u + f).normalized()), (12.0, 12.0, 12.5, 12.5)),
        (E + f * 14 * k, front_side(f), (12.0, 11.5, 12, 12)),
        (E + f * 45 * k, front_side(f), (11.5, 11.0, 11, 10.5)),
        (E + f * 80 * k, 0.45, (10.0, 9.5, 9, 8.5)),
        (E + f * 108 * k, 0.8, (9.5, 9.0, 7.5, 7.0)),
        (W, 1.0, (10.5, 10.5, 6.5, 6.5)),
        (W + d * 8 * k, 1.0, (13, 13, 7, 7)),
        (W + d * 19 * k, 1.0, (16, 16, 7, 7)),
        (W + d * 29 * k, 1.0, (17, 17, 6.5, 6.5)),
        (W + d * 36 * k, 1.0, (16, 16, 5.5, 5.5)),
        (W + d * 40 * k, 1.0, (10.5, 10.5, 3.5, 3.5)),
    ]
    # Twist the frame from the forearm into the hand: blend side hints toward w.
    fs = front_side(f)
    centers, hints, radii = [], [], []
    for c, h, r in secs:
        if isinstance(h, float):
            h = (fs * (1 - h) + w * h).normalized()
        centers.append(c)
        hints.append(h)
        radii.append(tuple(px(x) for x in r))
    sweep(bm, centers, hints, radii, n=12, cap0='pole', cap1='pole',
          cap0_len=px(2), cap1_len=px(2))
    build_fingers(bm, W, d, w, n)


# finger: (offset along w px, knuckle distance px, splay deg, segment lengths px, base radius px)
FINGERS = [
    (11.5, 36.0, 3.0, (15, 10.5, 9), 4.2),     # index
    (3.8, 38.5, -1.5, (16.5, 11.5, 9.5), 4.4),  # middle
    (-4.2, 37.0, -7.0, (14.5, 10, 8.5), 4.2),   # ring
    (-11.5, 34.0, -16.0, (11, 8, 7), 3.7),      # pinky
]
FINGER_CURL = 5.0  # degrees per joint, toward the palm


def _rot(v, axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, axis) @ v


def finger(bm, base, direction, bend_axis, seg_len, r0, r1, curl, n=8):
    pts = [base - direction * px(r0 * 0.6)]
    dirs = [direction]
    cur, dcur = base, direction
    pts.append(cur)
    dirs.append(dcur)
    for L in seg_len:
        dcur = _rot(dcur, bend_axis, curl)
        mid = cur + dcur * px(L * 0.5)
        cur = cur + dcur * px(L)
        pts += [mid, cur]
        dirs += [dcur, dcur]
    m = len(pts)
    radii = []
    for i in range(m):
        t = i / (m - 1)
        r = r0 + (r1 - r0) * t
        ra = px(r)
        radii.append((ra, ra, ra * 0.85, ra * 0.85))
    radii[0] = tuple(x * 0.8 for x in radii[0])
    # side hint = across the finger (in the palm plane), up = palm normal
    hints = [bend_axis.copy() for _ in dirs]
    sweep(bm, pts, hints, radii, n=n, cap0='pole', cap1='pole',
          cap0_len=px(1.0), cap1_len=px(r1 * 0.9))


def build_fingers(bm, W, d, w, n):
    k = px(1)
    for off, kd, splay, segs, r0 in FINGERS:
        base = W + d * kd * k + w * off * k + n * 0.5 * k
        direction = _rot(d, n, splay)       # splay within the palm plane
        axis = direction.cross(n).normalized()  # rotating about it bends toward +n (palm)
        finger(bm, base, direction, axis, segs, r0, r0 * 0.72, FINGER_CURL)
    # thumb: from the heel of the palm, angled toward the thumb side and palm
    base = W + d * 9 * k + w * 9 * k + n * 2.5 * k
    tdir = (d * 0.78 + w * 0.5 + n * 0.38).normalized()
    axis = tdir.cross(n).normalized()
    finger(bm, base, tdir, axis, (12, 10, 8), 5.0, 3.7, 10.0)


# ---------------------------------------------------------------- legs + feet
# Front view: row -> (outer, inner) offsets of the left leg from the midline.
# Side view: row -> (front y, back y). Measured every 10 rows on the reference
# (rows <= 620 are under the petticoat and extrapolated toward the hip).
LEG_FRONT = {
    455: (60, 6), 490: (64.5, 7), 530: (65.5, 10), 570: (65, 12.5), 600: (64.5, 14.5),
    630: (63, 16.5), 640: (61.5, 15.8), 650: (61.5, 16.5), 660: (63.5, 17.5),
    670: (65.5, 19.5), 680: (67.5, 20), 690: (69.5, 20.5), 700: (70.5, 20),
    710: (70.5, 19.5), 720: (69.5, 20.5), 730: (67.5, 22), 740: (65.5, 22),
    750: (63.5, 22.5), 760: (61, 23.5), 770: (58.5, 24), 780: (56, 24),
    790: (54, 24), 800: (51.5, 24), 810: (49.5, 23.5), 820: (46.5, 24),
    830: (45, 25), 842: (43, 27), 856: (41, 28),
}
LEG_SIDE = {
    455: (-50, 22), 490: (-48, 20), 530: (-46, 16), 570: (-44, 13), 600: (-42, 11),
    630: (-41, 9), 640: (-38.5, 10), 650: (-35.5, 12), 660: (-32, 15.5),
    670: (-30.5, 19), 680: (-30, 22), 690: (-29, 24), 700: (-28, 25),
    710: (-27, 25), 720: (-27, 23), 730: (-26, 23), 740: (-25, 21),
    750: (-24, 18), 760: (-24, 17), 770: (-23, 15), 780: (-23, 13),
    790: (-23, 11), 800: (-23, 8), 810: (-23, 6), 820: (-22, 5),
    830: (-21, 5), 842: (-18, 4), 856: (-15, 5),
}


def build_leg(bm):
    rows = sorted(LEG_FRONT)
    centers, hints, radii = [], [], []
    for row in rows:
        xo, xi = LEG_FRONT[row]
        yf, yb = LEG_SIDE[row]
        centers.append(P((xo + xi) / 2, (yf + yb) / 2, row))
        hints.append(Vector((1, 0, 0)))
        hw = (xo - xi) / 2 - MARGIN
        hd = (yb - yf) / 2 - MARGIN
        # side+ = outer, side- = inner, up+ = front, up- = back
        radii.append((px(hw), px(hw), px(hd), px(hd)))
    sweep(bm, centers, hints, radii, n=16, cap0='pole', cap1='pole',
          cap0_len=px(6), cap1_len=px(5), tangent=(0, 0, -1))


# Foot as vertical slices across the foot (heel -> toe), fitted inside the
# shoes part's shell (levi/parts/shoes.py STATIONS: centre x, half width,
# insole and toe-box rows, converted to plain panel rows) with ~2 px clearance,
# and to the instep skin visible in the shoe opening on ref/side.png.
# (y, centre x, half width, bottom row, top row)  panel px
FOOT = [
    (14, 30.5, 6.0, 896, 872),
    (8, 30.5, 9.5, 898, 862),
    (0, 30.5, 11.0, 899, 851),
    (-8, 30.0, 11.5, 909, 848),
    (-15, 29.5, 12.0, 926, 852),
    (-22, 28.5, 12.5, 941, 860),
    (-30, 27.0, 14.0, 944, 866),
    (-40, 26.5, 14.5, 944, 888),
    (-50, 25.5, 14.0, 944, 907),
    (-58, 24.5, 13.0, 944.5, 920),
    (-66, 23.0, 11.0, 945, 928.5),
    (-74, 21.0, 8.5, 945, 933),
    (-80, 19.5, 6.0, 945, 936),
    (-85, 18.0, 3.8, 945, 939.5),
]


def build_foot(bm):
    centers, radii = [], []
    for y, cx, hw, bot, top in FOOT:
        centers.append(P(cx, y, (bot + top) / 2))
        hh = px((bot - top) / 2)
        radii.append((px(hw), px(hw), hh, hh))
    hints = [Vector((1, 0, 0))] * len(FOOT)
    # slices normal to -Y: side = +X, up = +Z
    sweep(bm, centers, hints, radii, n=12, p=2.3, cap0='pole', cap1='pole',
          cap0_len=px(3), cap1_len=px(3), tangent=(0, -1, 0))


# ---------------------------------------------------------------- build
def _mirror_x(bm_src):
    """Append a mirrored (x -> -x) copy of all geometry in bm_src."""
    geom = bm_src.verts[:] + bm_src.edges[:] + bm_src.faces[:]
    dup = bmesh.ops.duplicate(bm_src, geom=geom)
    verts = [e for e in dup['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.scale(bm_src, vec=(-1, 1, 1), verts=verts)


def build(col):
    bm = bmesh.new()
    build_arm(bm)
    build_leg(bm)
    build_foot(bm)
    _mirror_x(bm)
    build_torso(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.new_object(col, 'body', bm, [common.toon_material('skin')])
    common.shade_smooth(obj, 75.0)
    common.add_outline(obj)
    # The inverted-hull outline encloses the mesh, so if the object casts
    # shadows the hull shadows the whole surface and it renders entirely in
    # the shade tone. Skin needs no cast shadows in the cel look.
    obj.visible_shadow = False
    return obj
