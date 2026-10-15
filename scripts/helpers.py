"""Blender 内で exec して使う共通関数。部屋の座標: x -2.77..1.60 / y 0.35..5.00 / 単位 m"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler

D = bpy.data
SC = bpy.context.scene


def coll(n):
    c = D.collections.get(n)
    if not c:
        c = D.collections.new(n)
        SC.collection.children.link(c)
    return c


def rm(*prefixes):
    for o in [o for o in D.objects if o.name.startswith(prefixes)]:
        D.objects.remove(o, do_unlink=True)


def mat(n, col=None, rough=0.6, metal=0.0, emit=None):
    m = D.materials.get(n)
    if m:
        return m
    m = D.materials.new(n)
    m.use_nodes = True
    b = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit[0], 1)
        b.inputs["Emission Strength"].default_value = emit[1]
    m.diffuse_color = (*col, 1)
    return m


def _finish(n, bm, c, m, smooth=False, loc=(0, 0, 0), rot=(0, 0, 0)):
    me = D.meshes.new(n)
    bm.to_mesh(me)
    bm.free()
    o = D.objects.new(n, me)
    c.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    if m:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return o


def bevel(o, w=0.004, seg=2):
    md = o.modifiers.new("Bevel", 'BEVEL')
    md.width = w
    md.segments = seg
    md.limit_method = 'ANGLE'
    md.angle_limit = math.radians(40)
    md.harden_normals = True
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def subsurf(o, lv=2):
    md = o.modifiers.new("Subsurf", 'SUBSURF')
    md.levels = lv
    md.render_levels = lv
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def box(n, lo, hi, c, m, bv=0.0, seg=2, rot=None, at=None):
    """lo/hi はワールド座標。rot/at を渡すと lo/hi をローカル寸法として at に置く"""
    lo = Vector(lo)
    hi = Vector(hi)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=hi - lo, verts=bm.verts)
    ctr = (lo + hi) / 2
    if at is not None:
        bmesh.ops.translate(bm, vec=ctr, verts=bm.verts)
        o = _finish(n, bm, c, m, loc=at, rot=rot or (0, 0, 0))
    else:
        o = _finish(n, bm, c, m, loc=ctr)
    if bv:
        bevel(o, bv, seg)
    return o


def cyl(n, p0, p1, r0, r1, c, m, seg=16, smooth=True):
    p0 = Vector(p0)
    p1 = Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r0, radius2=r1, depth=d.length)
    o = _finish(n, bm, c, m, smooth=False, loc=(p0 + p1) / 2, rot=d.to_track_quat('Z', 'Y').to_euler())
    if smooth:
        bevel(o, min(r0, r1) * 0.15 + 0.0005, 2)
    return o


def lathe(n, prof, loc, c, m, seg=28, cap=True):
    """prof: [(半径, 高さ)] を下から上へ。Z 軸まわりに回転体を作る"""
    bm = bmesh.new()
    rings = []
    for r, z in prof:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    if cap:
        bm.faces.new(reversed(rings[0]))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = _finish(n, bm, c, m, smooth=True, loc=loc)
    md = o.modifiers.new("Edge", 'EDGE_SPLIT')
    md.split_angle = math.radians(50)
    return o


def tube(n, pts, r, c, m, res=4):
    cu = D.curves.new(n, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = r
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new('NURBS')
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    sp.use_endpoint_u = True
    sp.order_u = min(4, len(pts))
    cu.resolution_u = 10
    o = D.objects.new(n, cu)
    c.objects.link(o)
    if m:
        cu.materials.append(m)
    return o


def group(n, objs, c, loc=(0, 0, 0), rotz=0.0, scale=1.0):
    """ローカル座標で作った部品を Empty にまとめて配置する"""
    e = D.objects.new(n, None)
    e.empty_display_size = 0.1
    c.objects.link(e)
    for o in objs:
        o.parent = e
    e.location = loc
    e.rotation_euler.z = rotz
    e.scale = (scale,) * 3
    return e


def grid_mesh(n, nx, ny, fn, c, m, close_u=False):
    """fn(u,v)->(x,y,z), u,v は 0..1"""
    bm = bmesh.new()
    vs = [[bm.verts.new(fn(i / nx, j / ny)) for j in range(ny + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(n, bm, c, m, smooth=True)


def solidify(o, t, offset=0.0):
    md = o.modifiers.new("Solidify", 'SOLIDIFY')
    md.thickness = t
    md.offset = offset
    return o


def pillow(n, w, h, t, c, m, loc, rot=(0, 0, 0), nx=14, ny=10, seed=0):
    """縫い目が細く中央がふくらんだ枕。w×h 平面、厚さ t"""
    rnd = random.Random(seed)
    bm = bmesh.new()
    def prof(u):
        a = abs(2 * u - 1)
        return (1 - a ** 2.6) ** 0.55
    layers = []
    for s in (1, -1):
        g = []
        for i in range(nx + 1):
            row = []
            for j in range(ny + 1):
                u, v = i / nx, j / ny
                z = s * t / 2 * prof(u) * prof(v)
                pull = 1 - 0.06 * (1 - prof(u) * prof(v))
                x = (u - 0.5) * w * (pull + 0.04 * abs(2 * v - 1) ** 3 * (1 if abs(2 * u - 1) > 0.8 else 0))
                y = (v - 0.5) * h * pull
                edge = i in (0, nx) or j in (0, ny)
                if not edge:
                    z += rnd.uniform(-1, 1) * t * 0.025
                row.append(None if (s == -1 and edge) else bm.verts.new((x, y, z)))
            g.append(row)
        layers.append(g)
    top, bot = layers
    for i in range(nx + 1):
        for j in range(ny + 1):
            if bot[i][j] is None:
                bot[i][j] = top[i][j]
    for g, flip in ((top, False), (bot, True)):
        for i in range(nx):
            for j in range(ny):
                q = (g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1])
                if len(set(q)) == 4:
                    try:
                        bm.faces.new(q[::-1] if flip else q)
                    except ValueError:
                        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = _finish(n, bm, c, m, smooth=True, loc=loc, rot=rot)
    subsurf(o, 2)
    return o


def book(n, c, m, loc, size, rotz=0.0, tilt=0.0, page=None):
    """size=(幅, 奥行, 厚み)。寝かせた本。ページは少し内側に入る"""
    w, d, t = size
    page = page or mat("paper_pages", (0.85, 0.80, 0.68), 0.9)
    cover = box(n, (-w / 2, -d / 2, 0), (w / 2, d / 2, t), c, m, 0.0015, at=loc, rot=(tilt, 0, rotz))
    pg = box(n + "_pages", (-w / 2 + 0.004, -d / 2 + 0.003, 0.003), (w / 2 + 0.0005, d / 2 - 0.003, t - 0.003), c, page, at=(0, 0, 0))
    pg.parent = cover
    return cover


def view(max_ok=True):
    pass


def leaf(n, L, W, c, m, loc, pitch, yaw, droop=0.25, fold=0.25, roll=0.0, round_=False):
    """付け根が原点、+Y に伸びる葉。pitch は上向き角、yaw は水平の向き"""
    def fn(u, v):
        if round_:
            w = W / 2 * math.sin(math.pi * min(1, u * 0.98 + 0.02)) ** 0.5
        else:
            w = W / 2 * (math.sin(math.pi * u ** 0.75) ** 0.8) * (1 - 0.25 * u)
        x = (v - 0.5) * 2 * w
        return (x, u * L, -droop * L * u * u + fold * abs(x))
    o = grid_mesh(n, 6, 4, fn, c, m)
    o.location = loc
    o.rotation_euler = Euler((pitch, roll, yaw), 'YXZ')
    o.rotation_mode = 'YXZ'
    solidify(o, 0.0015)
    return o


def pot(n, c, m, loc, r, h, soil=None):
    soil = soil or mat("soil", (0.03, 0.02, 0.015), 1.0)
    p = lathe(n, [(r * 0.72, 0), (r * 0.98, h * 0.9), (r * 1.04, h * 0.9), (r * 1.04, h), (r * 0.94, h), (r * 0.9, h * 0.9)], loc, c, m, cap=False)
    s = lathe(n + "_soil", [(0.0005, h * 0.9), (r * 0.92, h * 0.9)], loc, c, soil, cap=False)
    b = lathe(n + "_base", [(0.0005, 0.002), (r * 0.72, 0.002)], loc, c, m, cap=False)
    return [p, s, b]


def plant(n, c, loc, r=0.08, h=0.12, pot_m=None, leaf_m=None, style='bush', count=12, L=0.12, W=0.07, height=0.3, seed=0):
    rnd = random.Random(seed)
    leaf_m = leaf_m or mat("leaf_green", (0.05, 0.14, 0.04), 0.5)
    stem_m = mat("plant_stem", (0.08, 0.12, 0.04), 0.6)
    parts = pot(n + "_pot", c, pot_m or mat("ceramic_terracotta", (0.45, 0.18, 0.08), 0.8), (0, 0, 0), r, h)
    top = h * 0.9
    for i in range(count):
        yaw = 2 * math.pi * (i / count) + rnd.uniform(-0.4, 0.4)
        dx, dy = -math.sin(yaw), math.cos(yaw)
        if style == 'bush':
            t = rnd.uniform(0.35, 1.0)
            out = r * rnd.uniform(0.5, 1.6) * t
            p = Vector((dx * out, dy * out, top + height * t * rnd.uniform(0.7, 1.0)))
            pitch = rnd.uniform(0.1, 0.9)
            ll = L * rnd.uniform(0.7, 1.15)
            parts.append(tube(n + "_stem", [(dx * r * 0.2, dy * r * 0.2, top), (dx * out * 0.5, dy * out * 0.5, (top + p.z) / 2 + 0.02), tuple(p)], 0.0025, c, stem_m, 2))
            parts.append(leaf(n + "_leaf", ll, W * ll / L, c, leaf_m, p, pitch, yaw, rnd.uniform(0.1, 0.4), 0.2, rnd.uniform(-0.3, 0.3), round_=True))
        elif style == 'tall':
            t = (i + 1) / count
            z = top + height * (0.25 + 0.75 * t) * rnd.uniform(0.9, 1.05)
            out = r * rnd.uniform(0.3, 1.2) + 0.12 * t
            p = Vector((dx * out, dy * out, z))
            ll = L * rnd.uniform(0.75, 1.2)
            parts.append(tube(n + "_stem", [(dx * r * 0.15, dy * r * 0.15, top), (dx * out * 0.2, dy * out * 0.2, top + (z - top) * 0.6), tuple(p)], 0.005, c, stem_m, 2))
            parts.append(leaf(n + "_leaf", ll, W * ll / L, c, leaf_m, p, rnd.uniform(-0.2, 0.7), yaw, rnd.uniform(0.25, 0.6), 0.18, rnd.uniform(-0.4, 0.4)))
        elif style == 'trail':
            ln = height * rnd.uniform(0.45, 1.0)
            out = r * 1.05 + rnd.uniform(0, 0.03)
            pts = [(dx * r * 0.3, dy * r * 0.3, top), (dx * out, dy * out, top + 0.03)]
            k = int(ln / 0.07) + 2
            wob = rnd.uniform(0, 6)
            for j in range(1, k):
                s = j / (k - 1)
                pts.append((dx * (out + 0.02) + 0.025 * math.sin(wob + s * 5), dy * (out + 0.02) + 0.025 * math.cos(wob + s * 4), top - ln * s))
            parts.append(tube(n + "_vine", pts, 0.002, c, stem_m, 2))
            for q in pts[1:]:
                a = rnd.uniform(0, 2 * math.pi)
                parts.append(leaf(n + "_leaf", L * rnd.uniform(0.7, 1.1), W, c, leaf_m, q, rnd.uniform(-1.0, -0.2), a, 0.3, 0.2, rnd.uniform(-0.4, 0.4), round_=True))
    return group(n, parts, c, loc)


BOOK_COLS = [(0.10, 0.16, 0.10), (0.42, 0.15, 0.07), (0.62, 0.52, 0.36), (0.07, 0.10, 0.16), (0.30, 0.22, 0.10), (0.50, 0.35, 0.12), (0.14, 0.14, 0.13), (0.55, 0.42, 0.30)]


def book_mat(i):
    return mat(f"book_cover_{i % len(BOOK_COLS)}", BOOK_COLS[i % len(BOOK_COLS)], 0.7)


def upright_books(n, c, x0, x1, y_front, z, depth_axis='y', hmin=0.19, hmax=0.27, seed=0, lean_last=True):
    """棚板 z の上に、x0..x1 へ背表紙を手前(-y)に向けた本を並べる"""
    rnd = random.Random(seed)
    x = x0
    out = []
    i = 0
    while x < x1 - 0.02:
        t = rnd.uniform(0.018, 0.045)
        h = rnd.uniform(hmin, hmax)
        d = rnd.uniform(0.15, 0.20)
        if x + t > x1:
            break
        lean = 0.0
        if lean_last and x + t + 0.06 > x1:
            lean = -0.22
        b = box(n, (0, 0, 0), (t, d, h), c, book_mat(rnd.randrange(8)), 0.002, at=(x, y_front + rnd.uniform(0, 0.02), z), rot=(0, lean, 0))
        out.append(b)
        x += t + 0.001 + (0.05 if lean else 0)
        i += 1
    return out
