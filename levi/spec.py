"""Single source of truth for Levi's proportions, calibration and palette.

World frame: metres, Z up, character faces -Y, origin on the ground midway
between the feet. Character's left side is +X.

All landmarks were measured from ref/levi_threeview.png (1536x1024).
Sheet -> world:  z = (SHEET_GROUND_Y - row) / PX_PER_M
                 h = (col - SHEET_CENTER_X[view]) / PX_PER_M
                 front: h = +x (image right = character's left)
                 side:  h = +y (character faces image-left, i.e. -Y)
                 back:  h = -x
"""

# ---------------------------------------------------------------- calibration
VIEWS = ('front', 'side', 'back')
SHEET_GROUND_Y = 951          # sheet row of the shoe soles
SHEET_TOP_Y = 18              # sheet row of the hair top (ahoge)
PX_PER_M = 643.0
HEIGHT = (SHEET_GROUND_Y - SHEET_TOP_Y) / PX_PER_M   # ~1.451 incl. hair
SHEET_CENTER_X = {'front': 310, 'side': 776, 'back': 1222}
PANEL_W, PANEL_H = 640, 1024  # ref/<view>.png size; render.py renders at this size

# Ortho cameras. Side view looks from +X toward -X so the character faces
# image-left, as on the sheet.
CAMERAS = {
    'front': {'loc': (0.0, -6.0), 'rot_z_deg': 0.0},
    'side':  {'loc': (6.0, 0.0), 'rot_z_deg': 90.0},
    'back':  {'loc': (0.0, 6.0), 'rot_z_deg': 180.0},
}


def panel_px(view, p):
    """World point -> (col, row) pixel in ref/<view>.png."""
    x, y, z = p
    h = {'front': x, 'back': -x, 'side': y}[view]
    return (PANEL_W / 2 + h * PX_PER_M, SHEET_GROUND_Y - z * PX_PER_M)


def px_to_z(row):
    return (SHEET_GROUND_Y - row) / PX_PER_M


def px_to_h(px):
    """Horizontal pixel offset from panel centre -> metres."""
    return px / PX_PER_M


# ---------------------------------------------------------------- landmarks
# Heights (z, metres). Half-widths (x) from the front view, half-depths (y)
# from the side view; y_front is the most -Y point, y_back the most +Y.
L = {}  # filled below by _landmarks()


def _landmarks():
    # Rough first-pass readings (+-3 px). Parts should re-measure the
    # reference around their own region and may refine locally.
    z = px_to_z
    h = px_to_h
    d = {
        # head
        'hair_top_z': z(14),          # ahoge tip
        'head_top_z': z(30),          # top of the hair mass on the skull
        'eye_z': z(116),
        'eye_x': h(25),               # eye centre offset from midline
        'chin_z': z(161),
        'head_half_w': h(35),         # face half width at cheek level
        'head_center_y': -h(38),      # skull centre depth (side view, -Y = forward)
        'nose_tip_y': -h(95),
        # neck / torso
        'choker_z': z(176),
        'neck_half_w': h(15),
        'neck_center_y': -h(38),
        'shoulder_z': z(205),
        'shoulder_half_w': h(85),     # outer shoulder edge
        'bodice_top_z': z(245),       # sweetheart neckline centre
        'bust_half_w': h(59),
        'bust_front_y': -h(95),
        'chest_center_y': -h(45),
        'waist_z': z(330),            # bow centre
        'waist_half_w': h(36),
        'waist_center_y': -h(35),
        'hip_z': z(390),
        'skirt_hem_z': z(598),        # centre-front hem
        'skirt_hem_side_z': z(550),   # hem at the widest flare (front view)
        'skirt_hem_half_w': h(245),   # front view, widest flare
        'skirt_hem_front_y': -h(175),  # side view
        'skirt_hem_back_y': h(175),
        'petticoat_hem_z': z(620),
        # legs
        'crotch_z': z(460),
        'knee_z': z(700),             # the knee kink on the sheet / widest leg loop (was 740)
        'ankle_z': z(830),
        'leg_center_x': h(43),        # thigh/knee centre offset from midline
        'thigh_half_w': h(22),
        'knee_half_w': h(18),
        'ankle_half_w': h(10),
        'ankle_center_x': h(35),
        'toe_tip_x': h(22),
        # arms (A-pose, front view, character's left side; mirror for right)
        'shoulder_joint': (h(80), -h(40), z(215)),
        'elbow': (h(140), -h(30), z(335)),
        'wrist': (h(200), -h(20), z(455)),
        'fingertip': (h(285), -h(15), z(480)),
        # feet (side view: toe points -Y)
        'heel_back_y': h(15),
        'toe_tip_y': -h(95),
        'heel_height': h(55),
    }
    L.update(d)


_landmarks()


# ---------------------------------------------------------------- palette
# base = lit colour, shade = toon shadow colour, line = outline colour (sRGB).
#
# SHEET_PALETTE is what the sheet measures: base/shade are the lit and shadow
# k-means clusters of line-free boxes inside each zone of
# ref/levi_threeview.png; line is the median of the darkest ~3% of pixels
# across that zone's outline (the stroke core). levi/regions.py classifies the
# reference with these fixed colours, so retuning the render palette does not
# move the reference regions. PALETTE (below) is what toon.py renders.
SHEET_PALETTE = {
    'skin':        {'base': '#FEEAE1', 'shade': '#F3CDC2', 'line': '#9E7262'},
    'hair':        {'base': '#F1F0EF', 'shade': '#C1C7C1', 'line': '#6E7676'},
    'hair_tip':    {'base': '#76B48E', 'shade': '#619379', 'line': '#446E5A'},
    'eye':         {'base': '#8ABF94', 'shade': '#5A9970', 'line': '#293540'},
    'green':       {'base': '#2D8A3D', 'shade': '#1F6630', 'line': '#114923'},
    'leaf':        {'base': '#63C177', 'shade': '#439357', 'line': '#1E462C'},
    'dress':       {'base': '#FBFCF1', 'shade': '#CEDED0', 'line': '#59675F'},
    'dress_mint':  {'base': '#E1EADC', 'shade': '#C4D0C0', 'line': '#59675F'},
    'sleeve':      {'base': '#F4F9EC', 'shade': '#DAEBD7', 'line': '#46625C'},
    'sleeve_dark': {'base': '#558A62', 'shade': '#325F3E', 'line': '#13401F'},
    'petticoat':   {'base': '#FDE3DD', 'shade': '#F0C4BE', 'line': '#9F8780'},
    # Wrist frills: re-sampled in round 2 (front view, both wrists, 2-means on
    # pale low-chroma pixels): the painted shade is a warm grey, not pink.
    'cuff':        {'base': '#FCF8F0', 'shade': '#D4CCC5', 'line': '#5E625C'},
    'flower':      {'base': '#F6F6F4', 'shade': '#D2D3CD', 'line': '#22372D'},
    # Yellow flower centres: only ~12 px each on the sheet (front, rows 55-92
    # near cols 270 / 368): base/shade are the upper/lower lightness halves of
    # those pixels, line their darkest tenth.
    'flower_center': {'base': '#DFCC9D', 'shade': '#BEA978', 'line': '#7A6E45'},
    'shoe':        {'base': '#28663D', 'shade': '#1E5634', 'line': '#10391E'},
    # Tan shoe underside / inner lining (back view rows ~910-940 under the
    # arches, side view inside the heel): ~100 px, upper/lower lightness halves.
    'sole':        {'base': '#A69B82', 'shade': '#93866E', 'line': '#6B624C'},
    'mouth':       {'base': '#D88A86', 'shade': '#B86A66', 'line': '#7A3C3A'},
}

# Round-2 look-dev retune on the full model (toon.py renders PALETTE exactly):
#   hair_tip     lighter, less saturated: the average painted tip, not its
#                darkest end, so the rendered white-to-mint fade is not too strong
#   green, leaf  round 4: back most of the way to the sheet. The round-2
#                darkening made ribbons and leaves read dull and heavy next to
#                the painted ones; green keeps a little less chroma than the
#                sheet's lit cluster (thin ribbons), its shade is the sheet's;
#                leaf stays clearly lighter than green (#56B36C vs the
#                sheet's #63C177) so the leaves read as separate, lit forms
#   hair, dress  shade lighter: cast shadows and the per-key ramps
#                (toon.RAMP_BY_KEY) put more area in shade, and the sheet's
#                broad shade areas are paler than its darkest cluster
#   hair, dress  line a little lighter: stroke medians matched to the sheet's
PALETTE_TUNING = {
    'hair':     {'shade': '#CBD3CD', 'line': '#77817F'},
    'hair_tip': {'base': '#8CC0A2', 'shade': '#70A386'},
    'green':    {'base': '#2B803C', 'shade': '#1F6630'},
    'leaf':     {'base': '#56B36C', 'shade': '#3E8C52'},
    'dress':    {'shade': '#D5E2D4', 'line': '#63726A'},
}
PALETTE = {k: {**v, **PALETTE_TUNING.get(k, {})} for k, v in SHEET_PALETTE.items()}


# ---------------------------------------------------------------- parts
# Face budget per part (triangles counted as faces after triangulation is NOT
# required; budget is in polygons as Blender reports them).
BUDGET = {
    'body': 4000,
    'head': 3500,
    'hair_front': 3000,
    'hair_back': 6000,
    'accessories': 1500,
    'bodice': 2500,
    'skirt': 4000,
    'petticoat': 2500,
    'sleeves': 3000,
    'shoes': 1500,
}
TOTAL_BUDGET = 32000

# Outline (inverted hull) thickness in metres, per part default. The sheet's
# strokes are ~1-1.5 px at 643 px/m; the ortho renders are 1:1 with the panel,
# so a hull of OUTLINE_PX panel pixels reads as the same line weight.
OUTLINE_PX = 1.25
OUTLINE_WIDTH = OUTLINE_PX / PX_PER_M   # ~0.00194 m
