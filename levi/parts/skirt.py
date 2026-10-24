"""Outer skirt: knee-length white overskirt flaring from the waist in soft godet
folds down to a wavy, rolled hem. White at the waist fading to pale mint.

Shape: one cloth sheet parameterised by azimuth phi (0 = front centre, +phi
toward the character's left / +X) and t (0 = waist, 1 = hem).
- Each height has an egg-shaped section (half-width X, front depth Yf, back
  depth Yb, panel px) measured from the reference outlines (_SECTION).
- Per azimuth the hem has a height (HEM_ROW) and a radial fold offset
  (HEM_OFF). Both were fitted by levi/parts/_skirt_fit.py so that the hem's
  projections match the measured hem outlines of the front, side and back
  views (_FRONT_HEM / _SIDE_HEM / _BACK_HEM) at once. Fold offsets grow from 0
  at the waist to HEM_OFF at the hem, which gives the radiating godet folds and
  their cel-shadow streaks.
- The last rows roll inward (_CURL_*) and the sheet is solidified, so where a
  fold turns the inside of the hem shows in the shade tone, as on the sheet.

All reference measurements are in panel pixels (rows / columns of
ref/<view>.png; panel centre column = 320).
"""
import math

import bmesh
from mathutils import Vector

from .. import common, spec

# ---------------------------------------------------------------- reference
# Visible lower edge of the overskirt (the petticoat starts below it), measured
# column by column. Key = panel px from the panel centre (+ = image right).
# Front: image right = +X. Back: image right = -X. Side: image right = +Y.
FRONT_HEM = """
-245:540 -242:548 -234:556 -230:560 -226:554 -222:550 -218:550 -214:555 -210:559 -206:563
-202:565 -198:566 -194:565 -190:562 -186:550 -182:546 -178:550 -174:555 -170:559 -166:563
-162:568 -158:569 -154:575 -150:580 -146:583 -142:585 -138:587 -134:589 -130:590 -126:591
-122:592 -118:592 -114:592 -110:556 -106:553 -102:555 -98:542 -94:540 -90:540 -86:541
-82:542 -78:543 -74:544 -70:547 -66:549 -62:551 -58:566 -54:594 -50:598 -46:600 -42:602
-38:603 -34:605 -30:607 -26:609 -22:610 -18:611 -14:612 -10:612 -6:612 -2:612 2:606
6:594 10:596 14:598 18:599 22:601 26:603 30:603 34:604 38:604 42:604 46:603 50:602
54:600 58:598 62:595 66:551 70:548 74:546 78:544 82:543 86:542 90:541 94:540 98:541
102:553 106:556 110:555 114:591 118:592 122:592 126:591 130:590 134:590 138:588 142:586
146:579 150:572 154:565 158:561 162:563 166:560 170:556 174:553 178:549 182:545 186:549
190:562 194:566 198:566 202:565 206:563 210:561 214:557 218:553 222:549 226:552 230:561
234:557 240:550 246:540
"""
BACK_HEM = """
-245:545 -238:560 -234:573 -230:559 -226:563 -222:552 -218:550 -214:555 -210:560 -206:564
-202:567 -198:570 -194:572 -190:569 -186:559 -182:553 -178:553 -174:556 -170:557 -166:559
-162:561 -158:564 -154:565 -150:568 -146:570 -142:572 -138:575 -134:587 -130:586 -126:585
-122:587 -118:589 -114:590 -110:590 -106:590 -102:563 -98:557 -94:544 -90:546 -86:548
-82:550 -78:553 -74:555 -70:558 -66:574 -62:568 -58:568 -54:606 -50:607 -46:608 -42:610
-38:612 -34:614 -30:615 -26:617 -22:618 -18:618 -14:619 -10:619 -6:619 -2:619 2:619
6:618 10:618 14:595 18:593 22:584 26:581 30:578 34:574 38:571 42:567 46:564 50:562
54:558 58:556 62:553 66:551 70:549 74:546 78:548 82:565 86:583 90:588 94:589 98:590
102:590 106:590 110:590 114:589 118:588 122:586 126:589 130:590 134:574 138:571 142:568
146:566 150:566 154:563 158:561 162:559 166:556 170:554 174:551 178:556 182:568 186:572
190:572 194:571 198:569 202:565 206:561 210:556 214:551 218:546 222:550 226:555 230:559
234:571 240:555 246:543
"""
SIDE_HEM = """
-176:560 -172:575 -166:590 -162:601 -158:594 -154:586 -150:589 -146:593 -142:595 -138:596
-134:589 -130:592 -126:595 -122:597 -118:598 -114:587 -110:580 -106:581 -102:583 -98:584
-94:586 -90:587 -86:587 -82:588 -78:587 -74:586 -70:583 -66:580 -62:549 -58:549 -54:549
-50:550 -42:551 -34:570 -26:595 -18:601 -10:603 -2:604 2:604 6:604 10:603 14:603
18:602 22:600 26:598 30:573 34:552 38:548 42:545 46:542 50:539 54:537 58:535 62:533
66:531 70:530 74:529 78:529 82:533 86:545 90:550 94:555 98:589 102:589 106:588 110:586
114:584 118:580 122:576 126:571 130:565 134:559 138:554 142:549 146:546 150:549 154:560
158:561 162:556 168:546
"""

# Section per panel row: (row, half-width X, front depth Yf (toward -Y), back
# depth Yb (toward +Y)), outer cloth surface before folds. Front-view sides
# above row ~480 and the side-view back edge above ~480 are hidden by sleeves
# and hair, so those rows follow a smooth bell from the waist (tucked under the
# bodice) to the measured flare.
_SECTION = [
    (326, 33, 64, 2),
    (338, 50, 84, 16),
    (360, 78, 97, 34),
    (400, 118, 110, 62),
    (450, 160, 117, 94),
    (480, 188, 127, 117),
    (500, 214, 136, 136),
    (520, 235, 147, 152),
    (540, 249, 158, 165),
    (560, 252, 166, 165),
    (575, 253, 170, 160),
    (600, 254, 163, 150),
    (620, 254, 157, 142),
]
TOP_ROW = 326            # tucked under the bodice bottom edge
CURL_T = 0.12            # last fraction of the drop over which the hem rolls inward
CURL_PX = 8.0            # inward roll at the hem edge
N_RIPPLE = 14            # fine godet ripple for shading streaks (crest at front centre)
RIPPLE_PX = 5.0

N_PHI = 144
# rings: sparse near the waist (under the bodice), dense in the rolled hem
T_STEPS = (0.0, 0.12, 0.21, 0.32, 0.44, 0.56, 0.68, 0.79, 0.88, 0.94, 0.975, 1.0)
THICK = 0.0025

# Fitted by _skirt_fit.py; regenerate with
#   blender -b --factory-startup -P levi/parts/_skirt_fit.py -- --write
# (without --write it only prints the tables and the fit report).
# HEM_ROW[i]: panel row of the hem at phi = 2*pi*i/N_PHI.
# HEM_OFF[i]: radial fold offset (px) at the hem at the same azimuth.
HEM_ROW = [
    607, 596, 601, 604, 603, 600, 584, 550, 542, 541, 566, 592, 592, 591, 591, 591, 582, 563,
    553, 556, 572, 583, 586, 585, 585, 581, 565, 556, 550, 550, 556, 562, 561, 559, 555, 547,
    546, 554, 562, 569, 566, 558, 547, 543, 539, 536, 532, 529, 536, 551, 561, 573, 571, 557,
    555, 562, 571, 585, 588, 590, 584, 570, 553, 546, 547, 557, 576, 601, 609, 615, 617, 619,
    619, 610, 588, 577, 569, 562, 554, 548, 573, 591, 589, 587, 591, 579, 572, 568, 564, 558,
    553, 563, 573, 567, 558, 552, 547, 542, 543, 550, 563, 559, 551, 548, 546, 547, 548, 546,
    544, 543, 541, 541, 541, 542, 548, 554, 557, 550, 557, 563, 566, 566, 566, 565, 556, 548,
    557, 568, 577, 583, 587, 590, 592, 584, 558, 540, 541, 546, 557, 587, 601, 605, 610, 612
]
HEM_OFF = [
    6, 8, 10, 14, 16, 14, 4, -4, 0, 6, 8, 4, -2, -6, -10, -12, -12, -6, 4, 8, 10, 4, -2, -6,
    -10, -14, -12, -6, -6, -8, -12, -12, -12, -10, -4, 4, 8, 2, -4, -8, -12, -18, -20, -18, -14,
    -8, 0, 8, 14, 14, 8, 4, 2, 4, 4, -2, -10, -18, -26, -26, -24, -18, -10, 2, 8, 2, 0, 8, 10,
    8, 6, 4, 2, 0, -6, -6, -4, -2, 0, 4, 4, 6, 10, 10, 8, 4, 0, -2, 0, 2, 2, 0, 0, 4, 8, 10, 10,
    6, 2, 2, 4, 4, 4, 2, 2, 4, 6, 6, 6, 6, 4, 4, 4, 4, 4, 2, 2, 0, -4, -6, -8, -8, -6, -4, -2,
    0, 0, 0, 0, 2, 2, 0, -2, 0, 4, 4, 2, 0, 2, 8, 10, 10, 8, 6
]


def parse_table(s):
    out = []
    for tok in s.split():
        a, b = tok.split(':')
        out.append((float(a), float(b)))
    return sorted(out)


def interp(table, v):
    if v <= table[0][0]:
        return table[0][1]
    if v >= table[-1][0]:
        return table[-1][1]
    lo, hi = 0, len(table) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if table[mid][0] <= v:
            lo = mid
        else:
            hi = mid
    (a0, b0), (a1, b1) = table[lo], table[hi]
    return b0 + (b1 - b0) * (v - a0) / (a1 - a0)


_SEC_T = [[(r[0], r[k]) for r in _SECTION] for k in (1, 2, 3)]


def section(row):
    return tuple(interp(t, row) for t in _SEC_T)


def phi_of(i):
    return 2 * math.pi * i / N_PHI


def point_px(i, t, row_hem, off_hem):
    """Cloth point (x, y, row) in panel px for azimuth index i and t in [0, 1]."""
    phi = phi_of(i)
    row = TOP_ROW + t * (row_hem - TOP_ROW)
    X, Yf, Yb = section(row)
    c, s = math.cos(phi), math.sin(phi)
    x, y = X * s, -c * (Yf if c > 0 else Yb)
    r = math.hypot(x, y)
    ux, uy = x / r, y / r
    off = t ** 1.4 * (off_hem + RIPPLE_PX * math.cos(N_RIPPLE * phi))
    if t > 1.0 - CURL_T:
        k = 1.0 - (1.0 - t) / CURL_T
        off -= CURL_PX * k * k
    return x + ux * off, y + uy * off, row


def initial_hem():
    """Starting guess for the fit: blend of the view tables, no fold offsets."""
    front, back, side = (parse_table(s) for s in (FRONT_HEM, BACK_HEM, SIDE_HEM))
    rows = []
    X, Yf, Yb = section(560)
    for i in range(N_PHI):
        phi = phi_of(i)
        c = math.cos(phi)
        x, y = X * math.sin(phi), -c * (Yf if c > 0 else Yb)
        r_fb = interp(front, x) if c > 0 else interp(back, -x)
        w = c * c
        rows.append(w * r_fb + (1 - w) * interp(side, y))
    return rows, [0.0] * N_PHI


# ---------------------------------------------------------------- build
def build(col):
    rows, offs = (HEM_ROW, HEM_OFF) if HEM_ROW else initial_hem()
    rings = []
    for t in T_STEPS:
        ring = []
        for i in range(N_PHI):
            x, y, row = point_px(i, t, rows[i], offs[i])
            ring.append(Vector((spec.px_to_h(x), spec.px_to_h(y), spec.px_to_z(row))))
        rings.append(ring)
    bm = common.loft(rings, closed=True)
    # open sheet: make the normals point away from the body (outer cloth side)
    radial = sum(f.normal.dot(Vector((f.calc_center_median().x, f.calc_center_median().y, 0.0)))
                 for f in bm.faces)
    if radial < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)

    mat = common.toon_material('dress', gradient='dress_mint')
    obj = common.new_object(col, 'skirt', bm, [mat])
    sol = obj.modifiers.new('Thickness', 'SOLIDIFY')
    sol.thickness = THICK
    sol.offset = -1.0
    sol.use_even_offset = True
    sol.use_quality_normals = True
    common.apply_modifiers(obj)
    common.shade_smooth(obj, 60.0)
    common.set_gradient(obj, common.z_gradient(spec.px_to_z(420), spec.px_to_z(600)))
    common.add_outline(obj)
    # The inverted-hull outline encloses this closed shell; as a shadow caster
    # it would put the whole skirt in the toon shade tone. Cel shading here
    # comes from the fold normals, so the skirt casts no shadows.
    obj.visible_shadow = False
    return obj
