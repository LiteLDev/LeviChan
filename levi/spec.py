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
        'knee_z': z(740),
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
PALETTE = {
    'skin':        {'base': '#FBEDE6', 'shade': '#F2C9BE', 'line': '#B0786E'},
    'hair':        {'base': '#F2F3F2', 'shade': '#C9D3CF', 'line': '#7E8C88'},
    'hair_tip':    {'base': '#5FA37E', 'shade': '#3E7F5C', 'line': '#24513A'},
    'eye':         {'base': '#3E9A62', 'shade': '#1F6A3E', 'line': '#123D24'},
    'green':       {'base': '#2E8A3E', 'shade': '#1E6A2C', 'line': '#0F3E18'},
    'leaf':        {'base': '#3FA34D', 'shade': '#2A7A36', 'line': '#14461C'},
    'dress':       {'base': '#F7FAF2', 'shade': '#D9E8D6', 'line': '#7D9480'},
    'dress_mint':  {'base': '#DCEFD9', 'shade': '#BCD9BA', 'line': '#6E8E70'},
    'sleeve':      {'base': '#E8F3E2', 'shade': '#C6DEC0', 'line': '#6F8F6C'},
    'sleeve_dark': {'base': '#7DB88A', 'shade': '#5A9A6A', 'line': '#2C5A36'},
    'petticoat':   {'base': '#F6CFC6', 'shade': '#E9A99F', 'line': '#A86C63'},
    'cuff':        {'base': '#FBF7F0', 'shade': '#E6DCCF', 'line': '#8E8478'},
    'flower':      {'base': '#FFFFFF', 'shade': '#E3E6E2', 'line': '#7F8A84'},
    'shoe':        {'base': '#2C7A3A', 'shade': '#1B5726', 'line': '#0C3014'},
    'mouth':       {'base': '#D88A86', 'shade': '#B86A66', 'line': '#7A3C3A'},
}


# ---------------------------------------------------------------- parts
# Face budget per part (triangles counted as faces after triangulation is NOT
# required; budget is in polygons as Blender reports them).
BUDGET = {
    'body': 4000,
    'head': 3500,
    'hair_front': 3000,
    'hair_back': 5000,
    'accessories': 1500,
    'bodice': 2500,
    'skirt': 3500,
    'petticoat': 2500,
    'sleeves': 3000,
    'shoes': 1500,
}
TOTAL_BUDGET = 32000

# Outline (inverted hull) thickness in metres, per part default.
OUTLINE_WIDTH = 0.0022
