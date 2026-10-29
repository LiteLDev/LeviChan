"""Minimal PMX 2.0/2.1 reader (numpy), for the offline asset tools (tools/prep_hyacine_*.py).

read(path) -> dict: pos / nrm / uv (MMD frame, raw), bones / wts (4 slots, -1 = none), dtype,
sdef, edge, faces (n, 3), textures, mats (with nidx), bone_list (name, pos, parent, flags,
append, axis, ik...), morphs (vertex morphs carry offsets [(vi, dx, dy, dz)]), frames,
rigids, joints. Our frame is Blender (x, y, z) = MMD (x, z, y) * 0.08 with the triangle
winding reversed. The PMX itself stays outside the repo (see NOTICE).
"""
import struct
import numpy as np


class R:
    def __init__(self, data):
        self.d = data
        self.o = 0

    def take(self, fmt):
        v = struct.unpack_from('<' + fmt, self.d, self.o)
        self.o += struct.calcsize('<' + fmt)
        return v

    def arr(self, dtype, n):
        a = np.frombuffer(self.d, dtype=dtype, count=n, offset=self.o)
        self.o += a.nbytes
        return a


def read(path):
    r = R(open(path, 'rb').read())
    assert r.d[:4] == b'PMX '
    r.o = 4
    ver, = r.take('f')
    n, = r.take('B')
    g = r.take('%dB' % n)
    enc, addu, vsz, tsz, msz, bsz, mosz, rsz = g[:8]
    codec = 'utf-16-le' if enc == 0 else 'utf-8'

    def text():
        L, = r.take('i')
        s = r.d[r.o:r.o + L].decode(codec, 'replace')
        r.o += L
        return s

    def idx(sz, signed=True):
        f = {1: 'b', 2: 'h', 4: 'i'}[sz] if signed else {1: 'B', 2: 'H', 4: 'I'}[sz]
        return r.take(f)[0]

    name, name_en, comment, comment_en = text(), text(), text(), text()
    nv, = r.take('i')
    pos = np.zeros((nv, 3)); nrm = np.zeros((nv, 3)); uv = np.zeros((nv, 2))
    bones = np.full((nv, 4), -1, np.int32); wts = np.zeros((nv, 4))
    dtype = np.zeros(nv, np.int8); edge = np.zeros(nv)
    sdef = np.zeros((nv, 9))
    for i in range(nv):
        p = r.take('8f')
        pos[i] = p[0:3]; nrm[i] = p[3:6]; uv[i] = p[6:8]
        if addu:
            r.take('%df' % (4 * addu))
        t, = r.take('B'); dtype[i] = t
        if t == 0:
            bones[i, 0] = idx(bsz); wts[i, 0] = 1
        elif t == 1:
            bones[i, :2] = [idx(bsz), idx(bsz)]; w, = r.take('f'); wts[i, :2] = [w, 1 - w]
        elif t == 2 or t == 4:
            bones[i] = [idx(bsz) for _ in range(4)]; wts[i] = r.take('4f')
        elif t == 3:
            bones[i, :2] = [idx(bsz), idx(bsz)]; w, = r.take('f'); wts[i, :2] = [w, 1 - w]
            sdef[i] = r.take('9f')
        edge[i], = r.take('f')
    nf, = r.take('i')
    fdt = {1: np.uint8, 2: np.uint16, 4: np.int32}[vsz]
    faces = r.arr(fdt, nf).astype(np.int64).reshape(-1, 3)
    nt, = r.take('i')
    textures = [text() for _ in range(nt)]
    nm, = r.take('i')
    mats = []
    for _ in range(nm):
        m = {'name': text(), 'name_en': text()}
        m['diffuse'] = r.take('4f'); m['spec'] = r.take('4f'); m['amb'] = r.take('3f')
        m['flag'], = r.take('B'); m['edge_col'] = r.take('4f'); m['edge'], = r.take('f')
        m['tex'] = idx(tsz); m['sphere'] = idx(tsz); m['sphere_mode'], = r.take('B')
        shared, = r.take('B')
        m['toon'] = r.take('B')[0] if shared else idx(tsz)
        m['memo'] = text(); m['nidx'], = r.take('i')
        mats.append(m)
    nb, = r.take('i')
    bl = []
    for _ in range(nb):
        b = {'name': text(), 'name_en': text()}
        b['pos'] = r.take('3f'); b['parent'] = idx(bsz); b['layer'], = r.take('i')
        fl, = r.take('H'); b['flags'] = fl
        if fl & 1:
            b['tail_bone'] = idx(bsz)
        else:
            b['tail'] = r.take('3f')
        if fl & 0x300:
            b['append'] = (idx(bsz), r.take('f')[0])
        if fl & 0x400:
            b['axis'] = r.take('3f')
        if fl & 0x800:
            b['local'] = (r.take('3f'), r.take('3f'))
        if fl & 0x2000:
            r.take('i')
        if fl & 0x20:
            tgt = idx(bsz); loop, = r.take('i'); lim, = r.take('f'); nl, = r.take('i')
            links = []
            for _ in range(nl):
                lb = idx(bsz); hl, = r.take('B')
                lm = (r.take('3f'), r.take('3f')) if hl else None
                links.append((lb, lm))
            b['ik'] = (tgt, loop, lim, links)
        bl.append(b)
    # morphs (names + type + vertex offsets)
    nmo, = r.take('i')
    morphs = []
    for _ in range(nmo):
        mo = {'name': text(), 'name_en': text()}
        mo['panel'], mo['type'] = r.take('BB'); cnt, = r.take('i')
        t = mo['type']
        if t == 1:  # vertex
            offs = []
            for _ in range(cnt):
                vi = idx(vsz, signed=False) if vsz < 4 else idx(4)
                offs.append((vi,) + r.take('3f'))
            mo['offsets'] = offs
        elif t == 0 or t == 9:
            r.o += cnt * (msz + 4)
        elif t == 2:
            r.o += cnt * (bsz + 28)
        elif t in (3, 4, 5, 6, 7):
            r.o += cnt * (vsz + 16)
        elif t == 8:
            r.o += cnt * (msz + 1 + 4 * 28)
        elif t == 10:
            r.o += cnt * (rsz + 1 + 24)
        morphs.append(mo)
    # display frames
    nd, = r.take('i')
    frames = []
    for _ in range(nd):
        fr = {'name': text(), 'name_en': text()}
        fr['special'], = r.take('B'); ne, = r.take('i')
        el = []
        for _ in range(ne):
            t, = r.take('B')
            el.append((t, idx(bsz) if t == 0 else idx(mosz)))
        fr['elems'] = el
        frames.append(fr)
    nr, = r.take('i')
    rigids = []
    for _ in range(nr):
        rb = {'name': text(), 'name_en': text()}
        rb['bone'] = idx(bsz); rb['group'], = r.take('B'); rb['mask'], = r.take('H')
        rb['shape'], = r.take('B'); rb['size'] = r.take('3f'); rb['pos'] = r.take('3f'); rb['rot'] = r.take('3f')
        rb['mass'], rb['ldamp'], rb['adamp'], rb['rest'], rb['fric'] = r.take('5f')
        rb['mode'], = r.take('B')
        rigids.append(rb)
    nj, = r.take('i')
    joints = []
    for _ in range(nj):
        jt = {'name': text(), 'name_en': text()}
        jt['type'], = r.take('B'); jt['a'] = idx(rsz); jt['b'] = idx(rsz)
        jt['vals'] = r.take('24f')
        joints.append(jt)
    return dict(sdef=sdef, edge=edge, frames=frames, rigids=rigids, joints=joints, name=name, name_en=name_en, comment=comment, pos=pos, nrm=nrm, uv=uv,
                bones=bones, wts=wts, dtype=dtype, faces=faces, textures=textures,
                mats=mats, bone_list=bl, morphs=morphs, globals=g)
