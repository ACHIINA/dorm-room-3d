"""リアル版 段階R1: Poly Haven の実写スキャン PBR テクスチャに置き換える。Blender 内で exec する。

- UV はメートル単位で振り、素材ごとにスキャンの実寸(マニフェストの dimensions_mm)で繰り返す
- 剛体は最長辺(木目)を u にした箱投影、布のシミュレーション物は元の格子に沿った UV
- 色はスキャンの輝度の揺らぎを残し、平均色だけ参考画像の色に染め直す(target)
"""
import bpy, bmesh, os, json, glob, math
import numpy as np
from mathutils import Vector

D = bpy.data
ROOT = os.path.dirname(D.filepath)
PH = os.path.join(ROOT, "assets_polyhaven", "textures")
MAN = json.load(open(os.path.join(ROOT, "assets_polyhaven", "manifest.json")))

# 素材名: (スキャン, 平均色の目標(None で元の色), 粗さ倍率, 法線強さ, 追加設定)
SPEC = {
    "wood_walnut": ("american_walnut_veneer", (0.135, 0.066, 0.030), 0.85, 0.6, dict(coat=0.35, coat_rough=0.12, bump=0.0004)),
    "wood_walnut_dark": ("smoked_walnut_veneer", (0.055, 0.028, 0.014), 0.9, 0.6, dict(coat=0.25, coat_rough=0.15, bump=0.0004)),
    "floor_oak": ("plank_flooring_02", (0.21, 0.11, 0.05), 0.75, 0.8, dict(coat=0.2, coat_rough=0.2, bump=0.0008, sat=0.75)),
    "wall_plaster": ("plastered_wall_04", (0.63, 0.56, 0.46), 1.0, 0.45, dict(bump=0.0006)),
    "door_paint": ("plastered_wall_04", (0.70, 0.67, 0.60), 0.55, 0.15, dict(bump=0.0002)),
    "fabric_olive": ("rough_linen", (0.17, 0.20, 0.10), 1.0, 1.0, dict(sheen=0.5, bump=0.0015)),
    "fabric_sheet_white": ("cotton_jersey", (0.80, 0.77, 0.70), 1.0, 0.8, dict(sheen=0.35, bump=0.001)),
    "mattress": ("cotton_jersey", (0.78, 0.75, 0.68), 1.0, 0.6, dict(sheen=0.3, bump=0.001)),
    "fabric_rust_knit": ("knitted_fleece", (0.46, 0.14, 0.055), 1.0, 1.0, dict(sheen=0.4, bump=0.002)),
    "fabric_rust_velvet": ("velour_velvet", (0.40, 0.11, 0.042), 1.0, 0.7, dict(sheen=1.0, sheen_rough=0.3, bump=0.0008)),
    "fabric_cream_boucle": ("wool_boucle", (0.72, 0.64, 0.50), 1.0, 1.2, dict(sheen=0.5, bump=0.003)),
    "fabric_gray_wool": ("poly_wool_herringbone", (0.24, 0.26, 0.24), 1.0, 1.0, dict(sheen=0.5, bump=0.0015)),
    "fabric_pattern_pillow": ("quatrefoil_jacquard_fabric", (0.46, 0.22, 0.10), 1.0, 1.0, dict(sheen=0.4, bump=0.001)),
    "leather_green": ("fabric_leather_02", (0.075, 0.10, 0.05), 1.5, 0.8, dict(spec=0.3, bump=0.0004)),
    "leather_brown": ("brown_leather", (0.15, 0.065, 0.025), 0.9, 0.8, dict(bump=0.0004)),
    "fabric_canvas_olive": ("denim_fabric_04", (0.11, 0.12, 0.06), 1.0, 1.0, dict(sheen=0.2, bump=0.0012)),
    # 廊下(r6_hallway.py)
    "hall_carpet": ("dirty_carpet", (0.085, 0.10, 0.13), 1.0, 1.3, dict(bump=0.002)),
    "hall_wall_paint": ("plastered_wall_04", (0.72, 0.70, 0.64), 0.7, 0.35, dict(bump=0.0004)),
    "hall_door_oak": ("smoked_walnut_veneer", (0.33, 0.215, 0.12), 0.8, 0.5, dict(coat=0.3, coat_rough=0.2, bump=0.0003)),
    # 315 号室とラウンジ(r7_spaces.py)
    "fabric_navy_duvet": ("cotton_jersey", (0.05, 0.07, 0.15), 1.0, 0.9, dict(sheen=0.4, bump=0.001)),
    "fabric_mustard": ("rough_linen", (0.42, 0.28, 0.07), 1.0, 1.0, dict(sheen=0.5, bump=0.0015)),
    "lounge_sofa_fabric": ("poly_wool_herringbone", (0.15, 0.21, 0.23), 1.0, 1.0, dict(sheen=0.5, bump=0.0015)),
}
# 布のシミュレーション物: 名前 → (格子の nx, ny, 幅 m, 奥行 m)
CLOTH_GRIDS = {"Bed_Duvet": (80, 66, 2.08, 1.75), "Bed_Throw": (30, 70, 0.65, 1.34), "Arm_Blanket": (22, 46, 0.34, 1.0)}


def files(asset):
    d = os.path.join(PH, asset)
    def f(*keys):
        for k in keys:
            hit = glob.glob(os.path.join(d, f"*_{k}_2k.*"))
            if hit:
                return hit[0]
        raise FileNotFoundError(f"{asset}: {keys}")
    # 色の画像は素材によって diff / albedo と名前が違う
    return {"diff": f("diff", "albedo"), "nor": f("nor_gl"), "rough": f("rough"), "disp": f("disp")}


def load(path, noncolor=False):
    im = D.images.load(bpy.path.relpath(path), check_existing=True)
    if noncolor:
        im.colorspace_settings.name = 'Non-Color'
    return im


_mean = {}


def mean_lum(im):
    if im.name not in _mean:
        a = np.empty(im.size[0] * im.size[1] * 4, np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(-1, 4)[:, :3]
        # 画像の画素は sRGB の値なので、シェーダーと同じリニアに直してから平均する
        a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
        _mean[im.name] = float((a @ np.array([0.2126, 0.7152, 0.0722], np.float32)).mean())
    return _mean[im.name]


def build(mname, asset, target, rough_mul, nrm, extra):
    m = D.materials.get(mname) or D.materials.new(mname)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N = lambda t, x, y: (lambda n: (setattr(n, "location", (x, y)), n)[1])(nt.nodes.new(t))
    L = nt.links.new
    fs = files(asset)
    mm = MAN["dimensions_mm"][asset]
    tile = (mm[0] / 1000.0, mm[1] / 1000.0)

    uv = N("ShaderNodeUVMap", -1400, 0)
    uv.uv_map = "UVMap"
    mp = N("ShaderNodeMapping", -1200, 0)
    mp.inputs["Scale"].default_value = (1 / tile[0], 1 / tile[1], 1)
    L(uv.outputs["UV"], mp.inputs["Vector"])

    def tex(k, nc, y):
        t = N("ShaderNodeTexImage", -950, y)
        t.image = load(fs[k], nc)
        t.interpolation = 'Cubic' if k == "diff" else 'Linear'
        L(mp.outputs["Vector"], t.inputs["Vector"])
        return t

    td, tn, tr, th = tex("diff", False, 400), tex("nor", True, 0), tex("rough", True, -300), tex("disp", True, -600)
    bsdf = N("ShaderNodeBsdfPrincipled", 300, 0)
    out = N("ShaderNodeOutputMaterial", 600, 0)
    L(bsdf.outputs[0], out.inputs["Surface"])

    col = td.outputs["Color"]
    if extra.get("sat") is not None:
        hsv = N("ShaderNodeHueSaturation", -650, 500)
        hsv.inputs["Saturation"].default_value = extra["sat"]
        L(col, hsv.inputs["Color"])
        col = hsv.outputs["Color"]
    if target:
        # 輝度の揺らぎ(平均で正規化)×目標色
        bw = N("ShaderNodeRGBToBW", -650, 350)
        L(col, bw.inputs["Color"])
        k = N("ShaderNodeMath", -450, 350)
        k.operation = 'MULTIPLY'
        k.inputs[1].default_value = 1.0 / max(mean_lum(td.image), 1e-4)
        L(bw.outputs[0], k.inputs[0])
        sc = N("ShaderNodeVectorMath", -250, 350)
        sc.operation = 'SCALE'
        sc.inputs[0].default_value = target
        L(k.outputs[0], sc.inputs["Scale"])
        col = sc.outputs["Vector"]
    L(col, bsdf.inputs["Base Color"])

    rm = N("ShaderNodeMath", -450, -300)
    rm.operation = 'MULTIPLY'
    rm.use_clamp = True
    rm.inputs[1].default_value = rough_mul
    L(tr.outputs["Color"], rm.inputs[0])
    L(rm.outputs[0], bsdf.inputs["Roughness"])

    nm = N("ShaderNodeNormalMap", -450, 0)
    nm.inputs["Strength"].default_value = nrm
    nm.uv_map = "UVMap"
    L(tn.outputs["Color"], nm.inputs["Color"])
    bp = N("ShaderNodeBump", -150, -150)
    bp.inputs["Strength"].default_value = 1.0
    bp.inputs["Distance"].default_value = extra.get("bump", 0.001)
    L(th.outputs["Color"], bp.inputs["Height"])
    L(nm.outputs["Normal"], bp.inputs["Normal"])
    L(bp.outputs["Normal"], bsdf.inputs["Normal"])

    for key, sock in (("coat", "Coat Weight"), ("coat_rough", "Coat Roughness"), ("sheen", "Sheen Weight"), ("sheen_rough", "Sheen Roughness")):
        if key in extra:
            bsdf.inputs[sock].default_value = extra[key]
    if "sheen" in extra and "sheen_rough" not in extra:
        bsdf.inputs["Sheen Roughness"].default_value = 0.4
    if "sheen" in extra and target:
        # 光沢を白のままにすると布の色が薄まるので、布の色に寄せる
        bsdf.inputs["Sheen Tint"].default_value = (*[min(1.0, c * 2.2) for c in target], 1)
    if "spec" in extra:
        bsdf.inputs["Specular IOR Level"].default_value = extra["spec"]
    m.diffuse_color = (*(target or (0.5, 0.5, 0.5)), 1)
    return m


# ---------------- UV ----------------
def uv_layer(me):
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    return me.uv_layers.new(name="UVMap")


def uv_box(o, floor=False):
    """面の向きで投影軸を選び、最長辺(木目)を u にした実寸 UV"""
    me = o.data
    uv = uv_layer(me)
    co = [v.co for v in me.vertices]
    size = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
    grain = max(range(3), key=lambda i: size[i])
    sx = o.matrix_world.to_scale()
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [i for i in range(3) if i != ax]
        if floor:
            a, b = 0, 1
        elif grain == b:
            a, b = b, a
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (c[a] * sx[a], c[b] * sx[b])


def uv_grid(o, nx, ny, w, h):
    """格子(i 外側 / j 内側)で作った布に、元の平面の実寸 UV を振る"""
    me = o.data
    uv = uv_layer(me)
    for li, lp in enumerate(me.loops):
        vi = lp.vertex_index
        i, j = divmod(vi, ny + 1)
        uv.data[li].uv = (i / nx * w, j / ny * h)


# ---------------- 実行 ----------------
built = {}
for mname, (asset, target, rmul, nrm, extra) in SPEC.items():
    if mname in D.materials:
        built[mname] = build(mname, asset, target, rmul, nrm, extra)

targets = set(built) | {"rug_wool"}
n_box = n_grid = 0
for o in D.objects:
    if o.type != 'MESH' or not any(s.material and s.material.name in targets for s in o.material_slots):
        continue
    key = next((k for k in CLOTH_GRIDS if o.name.startswith(k) and not o.name.endswith("Fringe")), None)
    if key and len(o.data.vertices) == (CLOTH_GRIDS[key][0] + 1) * (CLOTH_GRIDS[key][1] + 1):
        uv_grid(o, *CLOTH_GRIDS[key])
        n_grid += 1
    else:
        uv_box(o, floor=(o.name == "Floor"))
        n_box += 1

# ラグ: 柄はそのまま、毛足の凹凸と粗さをカーペットのスキャンから足す
rug = D.materials["rug_wool"]
nt = rug.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
pattern = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and n.image.name == "tex_rug")
for n in [n for n in nt.nodes if n.name.startswith("carpet_")
          or (n.type in ('UVMAP', 'MAPPING', 'NORMAL_MAP', 'HUE_SAT', 'MIX') and not n.name.startswith("keep_"))
          or (n.type == "TEX_IMAGE" and n.image and n.image.name.startswith("dirty_carpet"))]:
    nt.nodes.remove(n)  # 前回の追加分(途中で止まった分も)を消す


def node(t, name):
    n = nt.nodes.new(t)
    n.name = "carpet_" + name
    return n


def sock(nd, ident, out=False):
    return next(x for x in (nd.outputs if out else nd.inputs) if x.identifier == ident)


fs = files("dirty_carpet")
mm = MAN["dimensions_mm"]["dirty_carpet"]
uvn = node("ShaderNodeUVMap", "uv")
uvn.uv_map = "UVMap"
mp = node("ShaderNodeMapping", "map")
mp.inputs["Scale"].default_value = (1000 / mm[0], 1000 / mm[1], 1)
nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])
tn = node("ShaderNodeTexImage", "nor")
tn.image = load(fs["nor"], True)
nt.links.new(mp.outputs["Vector"], tn.inputs["Vector"])
nm = node("ShaderNodeNormalMap", "nmap")
nm.uv_map = "UVMap"
nm.inputs["Strength"].default_value = 1.2
nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
tdf = node("ShaderNodeTexImage", "diff")
tdf.image = load(fs["diff"])
nt.links.new(mp.outputs["Vector"], tdf.inputs["Vector"])
hs = node("ShaderNodeHueSaturation", "gray")
hs.inputs["Saturation"].default_value = 0.0
hs.inputs["Value"].default_value = 0.9 / max(mean_lum(tdf.image), 1e-4)
nt.links.new(tdf.outputs["Color"], hs.inputs["Color"])
mix = node("ShaderNodeMix", "mul")
mix.data_type = 'RGBA'
mix.blend_type = 'MULTIPLY'
sock(mix, "Factor_Float").default_value = 0.55
nt.links.new(pattern.outputs["Color"], sock(mix, "A_Color"))
nt.links.new(hs.outputs["Color"], sock(mix, "B_Color"))
nt.links.new(sock(mix, "Result_Color", True), bsdf.inputs["Base Color"])
bsdf.inputs["Sheen Weight"].default_value = 0.6

print("pbr materials", len(built), "uv box", n_box, "uv grid", n_grid)
