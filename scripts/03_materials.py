"""段階3b: マテリアルをプロシージャル/画像テクスチャで作り直す。Blender 内で exec する。
木目は各オブジェクトのカスタムプロパティ grain_scale (最長辺方向が小さい倍率) で向きを決める。"""
import bpy, os, math, random

D = bpy.data
ROOT = os.path.dirname(D.filepath)


def img(name):
    i = D.images.get(name)
    if not i:
        i = D.images.load(os.path.join(ROOT, "textures", name + ".png"), check_existing=True)
        i.name = name
    return i


class T:
    """ノードツリーを組むための小さな道具"""

    def __init__(self, m):
        m.use_nodes = True
        self.t = m.node_tree
        for n in list(self.t.nodes):
            self.t.nodes.remove(n)
        self.x = 0

    def n(self, typ, _in=None, **inp):
        nd = self.t.nodes.new(typ)
        for k, v in (_in or {}).items():
            self.set(nd, k, v)
        nd.location = (self.x, 0)
        self.x += 200
        for k, v in inp.items():
            if k.startswith("_"):
                setattr(nd, k[1:], v)
            else:
                self.set(nd, k, v)
        return nd

    def sock(self, nd, key, out=False):
        coll = nd.outputs if out else nd.inputs
        if isinstance(key, int):
            return coll[key]
        for s in coll:
            if s.identifier == key and s.enabled:
                return s
        for s in coll:
            if s.name == key and s.enabled:
                return s
        for s in coll:
            if s.name == key:
                return s
        raise KeyError(f"{nd.bl_idname}.{key}")

    def set(self, nd, key, v):
        s = self.sock(nd, key)
        if isinstance(v, tuple) and len(v) == 2 and hasattr(v[0], "outputs"):
            self.t.links.new(self.sock(v[0], v[1], True), s)
        elif hasattr(v, "outputs"):
            self.t.links.new(v.outputs[0], s)
        elif isinstance(v, (tuple, list)) and len(v) == 3 and s.type == 'RGBA':
            s.default_value = (*v, 1)
        else:
            s.default_value = v

    def ramp(self, src, stops, out="Fac"):
        r = self.n("ShaderNodeValToRGB", Fac=src if isinstance(src, tuple) else (src, out))
        e = r.color_ramp.elements
        while len(e) > 2:
            e.remove(e[-1])
        for i, (p, c) in enumerate(stops):
            el = e[i] if i < 2 else e.new(p)
            el.position = p
            el.color = (*c, 1) if len(c) == 3 else c
        return r

    def mix(self, fac, a, b):
        m = self.n("ShaderNodeMix", _data_type='RGBA')
        self.set(m, "Factor_Float", fac)
        self.set(m, "A_Color", a)
        self.set(m, "B_Color", b)
        return (m, "Result_Color")

    def math(self, op, a, b=None):
        m = self.n("ShaderNodeMath", _operation=op)
        self.set(m, 0, a)
        if b is not None:
            self.set(m, 1, b)
        return m

    def coord(self, kind="Object"):
        tc = self.n("ShaderNodeTexCoord")
        return (tc, kind)

    def bump(self, h, strength=0.1, dist=0.01, normal=None):
        b = self.n("ShaderNodeBump", Strength=strength, Distance=dist, Height=h)
        if normal:
            self.set(b, "Normal", normal)
        return b

    def out(self, shader):
        o = self.n("ShaderNodeOutputMaterial")
        self.set(o, "Surface", shader)
        return o

    def bsdf(self, **kw):
        names = {"color": "Base Color", "rough": "Roughness", "metal": "Metallic", "normal": "Normal",
                 "coat": "Coat Weight", "coat_rough": "Coat Roughness", "sheen": "Sheen Weight",
                 "sheen_rough": "Sheen Roughness", "sss": "Subsurface Weight", "emit_col": "Emission Color",
                 "emit": "Emission Strength", "trans": "Transmission Weight", "ior": "IOR", "spec": "Specular IOR Level"}
        p = self.n("ShaderNodeBsdfPrincipled")
        for k, v in kw.items():
            self.set(p, names[k], v)
        return p


def M(name):
    m = D.materials.get(name) or D.materials.new(name)
    return m, T(m)


def viewport(m, col):
    m.diffuse_color = (*col, 1)


# ---------------- 木 ----------------
def wood(name, dark, mid, light, coat=0.35, rough=0.42, figure=1.0):
    m, t = M(name)
    tc = t.coord("Object")
    gs = t.n("ShaderNodeAttribute", _attribute_type='OBJECT', _attribute_name="grain_scale")
    v = t.n("ShaderNodeVectorMath", _operation='MULTIPLY', _in={0: tc, 1: (gs, "Vector")})
    warp = t.n("ShaderNodeTexNoise", Vector=v, Scale=0.35, Detail=2.0, Roughness=0.4)
    v2 = t.n("ShaderNodeVectorMath", _operation='ADD', _in={0: v, 1: (warp, "Color")})
    grain = t.n("ShaderNodeTexWave", Vector=v2, Scale=1.6, Distortion=2.2 * figure, Detail=3.0, **{"Detail Scale": 1.2})
    grain.wave_type = 'BANDS'
    grain.bands_direction = 'DIAGONAL'  # 縮めた長辺方向ではなく断面方向に縞を刻む
    fine = t.n("ShaderNodeTexNoise", Vector=v, Scale=14.0, Detail=8.0, Roughness=0.6)
    f = t.math('MULTIPLY', (grain, "Fac"), 0.5)
    f = t.math('ADD', f, t.math('MULTIPLY', (fine, "Fac"), 0.5))
    col = t.ramp(f, [(0.25, dark), (0.55, mid), (0.85, light)], out="Value")
    r = t.ramp(f, [(0.2, (rough + 0.1,) * 3), (0.8, (rough - 0.08,) * 3)], out="Value")
    b = t.bump((fine, "Fac"), 0.06, 0.002)
    p = t.bsdf(color=(col, "Color"), rough=(r, "Color"), coat=coat, coat_rough=0.18, normal=b)
    t.out(p)
    viewport(m, mid)
    return m


# ---------------- 布 ----------------
def fabric(name, col, sheen=0.5, rough=0.88, weave=280.0, bump=0.25, var=0.10, kind="weave", col2=None):
    m, t = M(name)
    tc = t.coord("Object")
    if kind == "weave":
        w1 = t.n("ShaderNodeTexWave", Vector=tc, Scale=weave, Distortion=0.4, _wave_type='BANDS', _bands_direction='X')
        w2 = t.n("ShaderNodeTexWave", Vector=tc, Scale=weave, Distortion=0.4, _wave_type='BANDS', _bands_direction='Y')
        h = t.math('MULTIPLY', (w1, "Fac"), (w2, "Fac"))
    elif kind == "knit":
        # 縦方向のリブと V 字の編み目
        sep = t.n("ShaderNodeSeparateXYZ", Vector=tc)
        u = t.math('MULTIPLY', (sep, "X"), weave)
        vv = t.math('MULTIPLY', (sep, "Y"), weave * 0.6)
        fr = t.math('FRACT', u)
        tri = t.math('ABSOLUTE', t.math('SUBTRACT', fr, 0.5))
        vv2 = t.math('ADD', vv, t.math('MULTIPLY', tri, 1.2))
        st = t.math('SINE', t.math('MULTIPLY', vv2, 6.283))
        rib = t.math('SINE', t.math('MULTIPLY', u, 6.283))
        h = t.math('MULTIPLY', t.math('ADD', st, 1.0), t.math('ADD', t.math('ABSOLUTE', rib), 0.3))
    elif kind == "boucle":
        vo = t.n("ShaderNodeTexVoronoi", Vector=tc, Scale=weave, _feature='F1')
        h = t.math('SUBTRACT', 1.0, (vo, "Distance"))
    else:  # velvet
        nz = t.n("ShaderNodeTexNoise", Vector=tc, Scale=weave, Detail=2.0)
        h = (nz, "Fac")
    big = t.n("ShaderNodeTexNoise", Vector=tc, Scale=4.0, Detail=4.0)
    shade = t.ramp((big, "Fac"), [(0.3, tuple(c * (1 - var) for c in col)), (0.7, tuple(min(1, c * (1 + var)) for c in col))])
    c = (shade, "Color")
    if col2:
        c = t.mix(t.math('MULTIPLY', h, 0.5), c, col2)
    b = t.bump(h, bump, 0.003)
    p = t.bsdf(color=c, rough=rough, sheen=sheen, sheen_rough=0.35, normal=b)
    t.out(p)
    viewport(m, col)
    return m


def simple(name, col, rough=0.5, metal=0.0, coat=0.0, noise_scale=0.0, bump=0.0, var=0.06, sss=0.0):
    m, t = M(name)
    c = col
    nb = None
    if noise_scale:
        tc = t.coord("Object")
        nz = t.n("ShaderNodeTexNoise", Vector=tc, Scale=noise_scale, Detail=6.0)
        c = (t.ramp((nz, "Fac"), [(0.3, tuple(x * (1 - var) for x in col)), (0.7, tuple(min(1, x * (1 + var)) for x in col))]), "Color")
        if bump:
            nb = t.bump((nz, "Fac"), bump, 0.002)
    kw = dict(color=c, rough=rough, metal=metal, coat=coat)
    if nb:
        kw["normal"] = nb
    if sss:
        kw["sss"] = sss
    t.out(t.bsdf(**kw))
    viewport(m, col)
    return m


def brushed_metal(name, col, rough=(0.18, 0.38), scale=40.0):
    m, t = M(name)
    tc = t.coord("Object")
    nz = t.n("ShaderNodeTexNoise", Vector=tc, Scale=scale, Detail=6.0)
    r = t.ramp((nz, "Fac"), [(0.3, (rough[0],) * 3), (0.7, (rough[1],) * 3)], out="Fac")
    tint = t.ramp((nz, "Fac"), [(0.3, tuple(x * 0.85 for x in col)), (0.8, col)])
    t.out(t.bsdf(color=(tint, "Color"), rough=(r, "Color"), metal=1.0))
    viewport(m, col)
    return m


def image_mat(name, image, axes=("Y", "Z"), emit=0.0, rough=0.6, flip_u=False, bump_img=None, sheen=0.0, coat=0.0):
    m, t = M(name)
    tc = t.coord("Generated")
    sep = t.n("ShaderNodeSeparateXYZ", Vector=tc)
    u = (sep, axes[0])
    if flip_u:
        u = t.math('SUBTRACT', 1.0, u)
    uv = t.n("ShaderNodeCombineXYZ", X=u, Y=(sep, axes[1]))
    tx = t.n("ShaderNodeTexImage", Vector=uv)
    tx.image = img(image)
    tx.interpolation = 'Cubic'
    kw = dict(color=(tx, "Color"), rough=rough, sheen=sheen, coat=coat)
    if bump_img:
        tb = t.n("ShaderNodeTexImage", Vector=uv)
        tb.image = img(bump_img)
        tb.image.colorspace_settings.name = 'Non-Color'
        kw["normal"] = t.bump((tb, "Color"), 1.0, 0.006)
    if emit:
        kw["emit_col"] = (tx, "Color")
        kw["emit"] = emit
    t.out(t.bsdf(**kw))
    m.diffuse_color = (0.6, 0.55, 0.5, 1)
    return m


def leaves(name):
    m, t = M(name)
    oi = t.n("ShaderNodeObjectInfo")
    c = t.ramp((oi, "Random"), [(0.0, (0.035, 0.10, 0.025)), (0.5, (0.06, 0.16, 0.035)), (1.0, (0.11, 0.21, 0.05))])
    tc = t.coord("Generated")
    vein = t.n("ShaderNodeTexWave", Vector=tc, Scale=3.0, Distortion=0.2, _wave_type='BANDS', _bands_direction='X')
    p = t.bsdf(color=(c, "Color"), rough=0.42, normal=t.bump((vein, "Fac"), 0.08, 0.002), coat=0.15)
    tr = t.n("ShaderNodeBsdfTranslucent", Color=(c, "Color"))
    mx = t.n("ShaderNodeMixShader", Fac=0.28, _in={1: p, 2: tr})
    t.out(mx)
    viewport(m, (0.06, 0.16, 0.035))
    return m


def floor_planks(name):
    m, t = M(name)
    tc = t.coord("Object")
    sep = t.n("ShaderNodeSeparateXYZ", Vector=tc)
    sw = t.n("ShaderNodeCombineXYZ", X=(sep, "Y"), Y=(sep, "X"))  # 板は奥行き方向(y)へ
    br = t.n("ShaderNodeTexBrick", Vector=sw, Scale=1.0, **{"Mortar Size": 0.0025, "Brick Width": 1.25, "Row Height": 0.135, "Bias": 0.0})
    br.offset = 0.37
    br.offset_frequency = 1
    br.squash_frequency = 1
    t.set(br, "Color1", (0.30, 0.30, 0.30))
    t.set(br, "Color2", (0.70, 0.70, 0.70))
    t.set(br, "Mortar", (0.0, 0.0, 0.0))
    stretch = t.n("ShaderNodeVectorMath", _operation='MULTIPLY', _in={0: sw, 1: (1.2, 45.0, 45.0)})
    warp = t.n("ShaderNodeTexNoise", Vector=stretch, Scale=0.8, Detail=3.0)
    v2 = t.n("ShaderNodeVectorMath", _operation='ADD', _in={0: stretch, 1: (warp, "Color")})
    grain = t.n("ShaderNodeTexWave", Vector=v2, Scale=1.4, Distortion=2.5, Detail=3.0, _wave_type='BANDS', _bands_direction='Y')
    plank = t.n("ShaderNodeSeparateColor", Color=(br, "Color"))
    f = t.math('ADD', t.math('MULTIPLY', (grain, "Fac"), 0.3), t.math('MULTIPLY', (plank, "Red"), 0.75))
    col = t.ramp(f, [(0.2, (0.17, 0.08, 0.035)), (0.5, (0.25, 0.125, 0.055)), (0.85, (0.33, 0.17, 0.08))], out="Value")
    gap = t.ramp((br, "Fac"), [(0.0, (1, 1, 1)), (0.5, (0.15, 0.15, 0.15))])
    cc = t.n("ShaderNodeMix", _data_type='RGBA', _blend_type='MULTIPLY')
    t.set(cc, "Factor_Float", 1.0)
    t.set(cc, "A_Color", (col, "Color"))
    t.set(cc, "B_Color", (gap, "Color"))
    scuff = t.n("ShaderNodeTexNoise", Vector=tc, Scale=3.0, Detail=10.0)
    r = t.ramp((scuff, "Fac"), [(0.3, (0.22,) * 3), (0.75, (0.45,) * 3)])
    b1 = t.bump(t.math('SUBTRACT', 1.0, (br, "Fac")), 0.4, 0.002)
    b2 = t.bump((grain, "Fac"), 0.04, 0.001, normal=b1)
    t.out(t.bsdf(color=(cc, "Result_Color"), rough=(r, "Color"), coat=0.25, coat_rough=0.25, normal=b2))
    viewport(m, (0.24, 0.12, 0.05))
    return m


def glass(name):
    m, t = M(name)
    # 参考画像に合わせ映り込みを抑える(IOR を下げて反射率を約0.2%に)
    t.out(t.bsdf(color=(0.92, 0.96, 0.96), rough=0.02, trans=1.0, ior=1.1))
    return m


def emission(name, image, strength=1.0, v_scale=1.0):
    """v_scale>1 で画像を板の下部に収め、上は最上段の色(空)を延長する"""
    m, t = M(name)
    tc = t.coord("Generated")
    sep = t.n("ShaderNodeSeparateXYZ", Vector=tc)
    uv = t.n("ShaderNodeCombineXYZ", X=(sep, "X"), Y=t.math('MULTIPLY', (sep, "Z"), v_scale))
    tx = t.n("ShaderNodeTexImage", Vector=uv)
    tx.image = img(image)
    tx.extension = 'EXTEND'
    e = t.n("ShaderNodeEmission", Color=(tx, "Color"), Strength=strength)
    t.out(e)
    return m


def vinyl(name):
    m, t = M(name)
    tc = t.coord("Object")
    w = t.n("ShaderNodeTexWave", Vector=tc, Scale=180.0, _wave_type='RINGS', _rings_direction='Z')
    t.out(t.bsdf(color=(0.008, 0.008, 0.008), rough=0.22, normal=t.bump((w, "Fac"), 0.15, 0.001)))
    return m


def glow_mat(name, col, strength):
    m, t = M(name)
    tc = t.coord("Object")
    nz = t.n("ShaderNodeTexNoise", Vector=tc, Scale=20.0)
    p = t.bsdf(color=col, rough=0.35, trans=0.0, emit_col=col, emit=strength)
    t.out(p)
    viewport(m, col)
    return m


def pattern_pillow(name):
    m, t = M(name)
    tc = t.coord("Generated")
    mp = t.n("ShaderNodeMapping", Vector=tc, Rotation=(0, 0, math.radians(45)))
    ch = t.n("ShaderNodeTexChecker", Vector=mp, Scale=7.0)
    t.set(ch, "Color1", (0.55, 0.20, 0.08))
    t.set(ch, "Color2", (0.75, 0.62, 0.45))
    wv = t.n("ShaderNodeTexWave", Vector=tc, Scale=9.0, Distortion=2.0, _wave_type='BANDS', _bands_direction='Y')
    c = t.mix(t.math('GREATER_THAN', (wv, "Fac"), 0.78), (ch, "Color"), (0.16, 0.18, 0.10))
    w1 = t.n("ShaderNodeTexWave", Vector=t.coord("Object"), Scale=250.0, _wave_type='BANDS', _bands_direction='X')
    t.out(t.bsdf(color=c, rough=0.9, sheen=0.5, normal=t.bump((w1, "Fac"), 0.2, 0.002)))
    viewport(m, (0.5, 0.3, 0.15))
    return m


# ================= 作成と割り当て =================
walnut = wood("wood_walnut", (0.11, 0.05, 0.022), (0.18, 0.085, 0.038), (0.25, 0.125, 0.058))
wood("wood_walnut_dark", (0.045, 0.02, 0.01), (0.075, 0.035, 0.016), (0.11, 0.055, 0.026), coat=0.2)
floor_planks("floor_oak")
simple("wall_plaster", (0.66, 0.58, 0.47), 0.92, noise_scale=30.0, bump=0.03, var=0.04)
simple("door_paint", (0.70, 0.67, 0.60), 0.45, noise_scale=40.0, bump=0.01, var=0.02)
simple("window_frame_bronze", (0.035, 0.03, 0.025), 0.4, metal=0.6, noise_scale=30.0, var=0.1)
glass("window_glass")
emission("night_campus", "tex_night_campus", 1.0, v_scale=15.25 / 12.8)

brushed_metal("metal_brass", (0.80, 0.58, 0.26))
brushed_metal("metal_aluminum", (0.70, 0.70, 0.72), (0.25, 0.4))
simple("plastic_black", (0.018, 0.018, 0.018), 0.45, noise_scale=200.0, bump=0.02)
fabric("speaker_grill", (0.03, 0.03, 0.03), 0.3, 0.95, weave=600)
simple("speaker_cone", (0.03, 0.03, 0.03), 0.7)
simple("keyboard_keys", (0.10, 0.10, 0.10), 0.55)
fabric("felt_deskmat", (0.07, 0.07, 0.065), 0.2, 0.98, weave=800, kind="velvet", bump=0.1)
simple("leather_green", (0.10, 0.13, 0.07), 0.45, noise_scale=300.0, bump=0.08, var=0.08, coat=0.2)
simple("leather_brown", (0.17, 0.075, 0.03), 0.5, noise_scale=300.0, bump=0.06, var=0.1)

fabric("fabric_olive", (0.20, 0.23, 0.12), 0.6, 0.85, weave=320, bump=0.15)
fabric("fabric_sheet_white", (0.82, 0.79, 0.72), 0.4, 0.8, weave=380, bump=0.1, var=0.03)
fabric("fabric_rust_knit", (0.50, 0.16, 0.06), 0.7, 0.9, weave=55, bump=0.6, kind="knit", var=0.08)
fabric("fabric_rust_velvet", (0.43, 0.12, 0.045), 1.0, 0.8, weave=150, bump=0.05, kind="velvet", var=0.12)
fabric("fabric_gray_wool", (0.25, 0.27, 0.25), 0.6, 0.95, weave=70, bump=0.5, kind="knit")
fabric("fabric_cream_boucle", (0.74, 0.66, 0.52), 0.5, 0.95, weave=160, bump=0.5, kind="boucle")
fabric("fabric_canvas_olive", (0.13, 0.14, 0.075), 0.2, 0.9, weave=220, bump=0.3)
pattern_pillow("fabric_pattern_pillow")

simple("ceramic_cream", (0.80, 0.74, 0.62), 0.25, coat=0.6, noise_scale=80.0, var=0.03)
simple("ceramic_dark", (0.05, 0.06, 0.055), 0.3, coat=0.5, noise_scale=120.0, var=0.25)
simple("ceramic_terracotta", (0.50, 0.22, 0.10), 0.85, noise_scale=25.0, bump=0.05, var=0.12)
simple("soil", (0.03, 0.02, 0.015), 1.0, noise_scale=150.0, bump=0.3, var=0.3)
leaves("leaf_green")
simple("plant_stem", (0.08, 0.12, 0.04), 0.6)
simple("cork_board", (0.50, 0.33, 0.18), 0.95, noise_scale=500.0, bump=0.4, var=0.25)
simple("paper_white", (0.86, 0.84, 0.79), 0.9, noise_scale=50.0, var=0.02)
simple("paper_pages", (0.84, 0.78, 0.64), 0.9, noise_scale=400.0, bump=0.05, var=0.04)
simple("frame_black", (0.02, 0.02, 0.02), 0.5, noise_scale=60.0, var=0.2)
simple("notebook_kraft", (0.45, 0.32, 0.18), 0.8, noise_scale=200.0, bump=0.05, var=0.08)
simple("pin_red", (0.5, 0.04, 0.03), 0.25, coat=0.5)
simple("stone_white", (0.72, 0.70, 0.66), 0.3, coat=0.3, noise_scale=8.0, var=0.08)
simple("mattress", (0.80, 0.77, 0.70), 0.85)
vinyl("vinyl_black")
glow_mat("lamp_globe_glass", (1.0, 0.72, 0.42), 6.0)
glow_mat("lamp_bulb", (1.0, 0.78, 0.5), 25.0)
image_mat("monitor_screen", "tex_wallpaper", ("Y", "Z"), emit=1.5, rough=0.15)
image_mat("rug_wool", "tex_rug", ("X", "Y"), rough=1.0, bump_img="tex_rug_bump", sheen=0.6)
image_mat("art_poster_circle", "tex_poster_circle", ("Y", "Z"), rough=0.75)
image_mat("art_poster_shapes", "tex_poster_shapes", ("X", "Z"), rough=0.75)
image_mat("art_photo_campus1", "tex_photo_campus1", ("X", "Z"), rough=0.4, coat=0.5)
image_mat("art_photo_campus2", "tex_photo_campus2", ("X", "Z"), rough=0.4, coat=0.5)
for i in range(8):
    image_mat(f"pinned_photo_{i}", f"tex_pinned_{i}", ("Y", "Z"), rough=0.35)
for i in range(8):
    m = D.materials.get(f"book_cover_{i}")
    if m:
        col = tuple(m.diffuse_color)[:3]
        simple(m.name, col, 0.6, noise_scale=120.0, bump=0.03, var=0.08)
for m in [m for m in D.materials if m.name.startswith("record_sleeve_")]:
    simple(m.name, tuple(m.diffuse_color)[:3], 0.7, noise_scale=60.0, var=0.1)

# ---- ブロックアウト素材を置き換える ----
swap = {"BO_wall": "wall_plaster", "BO_floor": "floor_oak", "BO_windowframe": "window_frame_bronze",
        "BO_mattress": "mattress", "BO_wood": "wood_walnut", "BO_bedding": "fabric_olive", "BO_throw": "fabric_rust_knit"}


def assign(o, new):
    for s in o.material_slots:
        s.material = new


for o in D.objects:
    if o.type not in ('MESH', 'CURVE'):
        continue
    for s in o.material_slots:
        if s.material and s.material.name in swap:
            s.material = D.materials[swap[s.material.name]]
        if s.material and s.material.name.startswith("photo_"):
            s.material = D.materials[f"pinned_photo_{random.randrange(8)}"]
for n in ("Door_Leaf",):
    assign(D.objects[n], D.materials["door_paint"])
for o in D.objects:
    if o.name.startswith(("Door_Jamb", "Baseboard")):
        assign(o, D.materials["door_paint"])

# ---- 窓ガラスと外の夜景 ----
for n in ("Win_Glass", "Backdrop_NightCampus"):
    o = D.objects.get(n)
    if o:
        D.objects.remove(o, do_unlink=True)
import bmesh
W = D.collections["02_Window"]


def plane(n, x0, x1, y, z0, z1, m):
    me = D.meshes.new(n)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))]
    bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    o = D.objects.new(n, me)
    W.objects.link(o)
    me.materials.append(m)
    return o


g = plane("Win_Glass", -0.95, 1.56, 5.0 + 0.212, 0.93, 2.50, D.materials["window_glass"])
md = g.modifiers.new("Solidify", 'SOLIDIFY')
md.thickness = 0.006  # 厚みがないと屈折が戻らず外の景色が歪む
# 画像の地面(v=0.16)が窓台の視線、建物の上端が窓の下半分に来る縮尺
bd = plane("Backdrop_NightCampus", -10.3, 15.3, 40.0, -2.45, 12.8, D.materials["night_campus"])
bd.visible_shadow = False

# ---- 木目の向き ----
wood_names = {"wood_walnut", "wood_walnut_dark"}
for o in D.objects:
    if o.type != 'MESH' or not any(s.material and s.material.name in wood_names for s in o.material_slots):
        continue
    bb = [v for v in o.bound_box]
    dims = [max(v[i] for v in bb) - min(v[i] for v in bb) for i in range(3)]
    ax = dims.index(max(dims))
    sc = [70.0, 70.0, 70.0]
    sc[ax] = 1.2
    o["grain_scale"] = sc
print("materials ok", len(D.materials))
