"""Write the skirt drape's reference solve (rig.DRAPE_REF), which every rig build continues from.

    blender -b out/levi.blend -P tools/drape_ref.py -- [--out assets/drape/drape_ref.npz] [--no-check]

Builds the rig on the (unrigged) model until rig._skirt_drape is called and solves the drape there
from scratch (rig._skirt_drape(..., record=...): the round-11 solve, binned cloth, first crossings,
the gather's descent), recording each clearance call's turns before the zigzag pass, their margins
over the threshold on the full cloth (rig._drape_cloth, rig._drape_track), the gather's yaw and root
lift per thigh pitch and the final tables. Then (unless --no-check) it continues from the new
reference on the same inputs, which must give the same tables bit for bit, and writes the npz
(deterministic: same model, same file). Run it when a lane wants the drape's discrete choices made
again (the build log says how far the tables moved from the reference's), then check the drape.
"""
import os
import sys
import time

import bpy  # noqa: F401  (run inside Blender)
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levi import rig  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(ROOT, rig.DRAPE_REF)
CHECK = True
while argv:
    k = argv.pop(0)
    if k == '--out':
        OUT = os.path.abspath(argv.pop(0))
    elif k == '--no-check':
        CHECK = False


class _Stop(Exception):
    pass


CAP = {}
_orig = rig._skirt_drape


def _grab(chains, pts, cy, hip, knee, body, inner=None, record=None):
    CAP.update(chains=chains, pts=pts, cy=cy, hip=hip, knee=knee, body=body, inner=inner)
    raise _Stop()


def main():
    t0 = time.time()
    rig._skirt_drape = _grab
    try:
        rig.build_rig()
    except _Stop:
        pass
    rig._skirt_drape = _orig
    if not CAP:
        sys.exit('drape_ref: the rig build never reached the skirt drape')
    print('drape_ref: inputs captured (%.0f s)' % (time.time() - t0), flush=True)
    rec = {}
    out = rig._skirt_drape(CAP['chains'], CAP['pts'], CAP['cy'], CAP['hip'], CAP['knee'], CAP['body'],
                           inner=CAP['inner'], record=rec)
    print('drape_ref: solved from scratch, %d clearance calls, %d gathers (%.0f s)' % (
        len(rec['t_ref']), len(rec['psi_ref']), time.time() - t0), flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp.npz'
    np.savez_compressed(tmp, **rec)
    if CHECK:
        rig.DRAPE_REF, keep = tmp, rig.DRAPE_REF
        rig._DRAPE_REF_CACHE.clear()
        out2 = rig._skirt_drape(CAP['chains'], CAP['pts'], CAP['cy'], CAP['hip'], CAP['knee'], CAP['body'],
                                inner=CAP['inner'])
        rig.DRAPE_REF = keep
        rig._DRAPE_REF_CACHE.clear()
        d = float(np.abs(rig._drape_flat(out2) - rig._drape_flat(out)).max())
        print('drape_ref: continued from it on the same inputs: tables differ by %.3g rad (%.0f s)' % (
            d, time.time() - t0), flush=True)
        if d != 0.0:
            os.remove(tmp)
            sys.exit('drape_ref: the continuation does not reproduce the reference; not written')
    os.replace(tmp, OUT)
    print('drape_ref: wrote', OUT, '(%.0f KB)' % (os.path.getsize(OUT) / 1024), flush=True)


main()
