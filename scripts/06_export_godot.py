"""段階6: Godot で歩き回れるように書き出す。
実行: blender -b dorm_room.blend --python scripts/render_gpu.py --python scripts/06_export_godot.py
dorm_room.blend は保存しない(読み込んだものを変換して .glb と Godot プロジェクトを書くだけ)。

1. 計算で作っているマテリアルを平面にベイクしてタイル画像にする
2. モディファイアとカーブをメッシュに確定する
3. 全オブジェクトに UV を付ける(画像系は Generated 座標、他は実寸の箱投影)
4. glTF 向けの単純な Principled マテリアルへ置き換えて .glb を書き出す
5. 照明の位置を Godot 座標に変換して main.tscn などを書く
"""
import bpy, bmesh, os, math, random, json
from mathutils import Vector, Matrix

D = bpy.data
SC = bpy.context.scene
ROOT = os.path.dirname(D.filepath)
OUT = os.path.join(ROOT, "godot_walk")
TEXOUT = os.path.join(OUT, "assets", "textures")
os.makedirs(TEXOUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "scripts"), exist_ok=True)
random.seed(1)


def g(v):
    """Blender(Z上) → Godot(Y上)"""
    return Vector((v.x, v.z, -v.y))


# ---------------- 照明の位置を控える ----------------
def light_info(name):
    o = D.objects[name]
    mw = o.matrix_world
    return {"pos": g(mw.translation), "dir": g((mw.to_3x3() @ Vector((0, 0, -1))).normalized())}


LI = {k: light_info(n) for k, n in {"lamp": "Light_DeskLamp_Spot", "globe": "Light_Globe", "monitor": "Light_Monitor",
                                     "moon": "Light_Moon", "window": "Light_Window", "bounce": "Light_Bounce_Warm"}.items()}

# カメラ・ライト・置き換え済み・空気の霞(ボリューム)は書き出さない
_old = set(D.collections["90_Replaced"].all_objects) if "90_Replaced" in D.collections else set()
for o in list(D.objects):
    if o.type in ('CAMERA', 'LIGHT') or o in _old or o.name in ("Atmos_Haze", "Backdrop_NightCampus"):
        D.objects.remove(o, do_unlink=True)

# ---------------- 1. ベイク ----------------
# 名前: (タイルの実寸 m, 解像度, 法線もベイクするか)
BAKE = {
    "wood_walnut": (1.0, 2048, True), "wood_walnut_dark": (1.0, 1024, True), "floor_oak": (2.5, 2048, True),
    "wall_plaster": (1.0, 1024, True), "door_paint": (1.0, 512, False),
    "fabric_olive": (0.25, 1024, True), "fabric_sheet_white": (0.25, 1024, True), "fabric_rust_knit": (0.25, 1024, True),
    "fabric_rust_velvet": (0.5, 1024, True), "fabric_gray_wool": (0.25, 1024, True), "fabric_cream_boucle": (0.25, 1024, True),
    "fabric_canvas_olive": (0.25, 1024, True), "felt_deskmat": (0.3, 512, True), "speaker_grill": (0.1, 512, True),
    "leather_green": (0.3, 512, True), "leather_brown": (0.3, 512, True), "cork_board": (0.3, 1024, True),
    "ceramic_terracotta": (0.5, 512, True), "paper_pages": (0.2, 512, True),
    "fabric_pattern_pillow": (1.0, 512, False),
    "hall_ceiling_tile": (1.2, 1024, True),
    "tile_wall_white": (0.6, 1024, True), "tile_floor_gray": (0.6, 1024, True),  # Generated 座標の柄なので平面 0..1 に焼けば UV と一致する
}
# リアル版: 実写スキャンの PBR 素材(タイルの実寸 m)。色・法線・粗さの 3 枚をベイクする
_r1 = {}
exec(open(os.path.join(ROOT, "scripts", "r1_pbr.py")).read().split("# ---------------- 実行 ----------------")[0], _r1)
PBR = {}
for _m, (_asset, *_rest) in _r1["SPEC"].items():
    if _m in D.materials:
        _mm = _r1["MAN"]["dimensions_mm"][_asset]
        PBR[_m] = (_mm[0] / 1000.0, _mm[1] / 1000.0)
for _m in PBR:
    BAKE.pop(_m, None)
# Poly Haven の物(元の UV と画像のマテリアルをそのまま使う): 植物・小物と、R8 の家具
PH_OBJS = set(D.collections["20_PolyHaven"].all_objects) if "20_PolyHaven" in D.collections else set()
if "27_Furniture" in D.collections:
    PH_OBJS |= {o for o in D.collections["27_Furniture"].all_objects if not o.name.startswith("FLounge_Game")}
PH_MATS = {s.material.name for o in PH_OBJS if o.type == 'MESH' for s in o.material_slots if s.material}

IMAGE_MATS = {
    "calendar_page": ("Y", "Z"),  # Godot で描いたカレンダーを貼る
    # 廊下の貼り紙とホワイトボード(向かいの壁の分は反転済みの画像 _m)
    **{n: ("X", "Z") for n in ("flyer_meeting", "flyer_study", "flyer_quiet", "flyer_soccer", "whiteboard_0", "whiteboard_1_m", "whiteboard_2_m", "whiteboard_2")},
    "poster_band": ("Y", "Z"), "poster_film_m": ("Y", "Z"),  # 315 号室の左右の壁
    "tv_screen": ("Y", "Z"),  # ラウンジのテレビ(画面全体で 1 枚。左右の反転は Godot 側)  # 名前: Generated 座標のどの軸を u, v にするか
    "rug_wool": ("X", "Y"), "art_poster_circle": ("Y", "Z"), "art_poster_shapes": ("X", "Z"),
    "art_photo_campus1": ("X", "Z"), "art_photo_campus2": ("X", "Z"), "monitor_screen": ("Y", "Z"),
    "night_campus": ("X", "Z"), "fabric_pattern_pillow": ("X", "Y"),
}
for i in range(8):
    IMAGE_MATS[f"pinned_photo_{i}"] = ("Y", "Z")

SC.render.engine = 'CYCLES'
SC.cycles.samples = 4
SC.cycles.use_denoising = False
SC.render.bake.margin = 0

me = D.meshes.new("BakePlane")
bm = bmesh.new()
uvl = bm.loops.layers.uv.new("UVMap")
vs = [bm.verts.new(v) for v in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
f = bm.faces.new(vs)
for lp, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
    lp[uvl].uv = uv
bm.to_mesh(me)
bm.free()
plane = D.objects.new("BakePlane", me)
SC.collection.objects.link(plane)
# 焼き付け先は常に画像全体(0..1)。素材が読む UVMap とは別の UV を有効にしておく
_bk = me.uv_layers.new(name="BakeUV")
for lp, uv in zip(_bk.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
    lp.uv = uv
me.uv_layers.active = _bk
plane["grain_scale"] = [1.2, 70.0, 70.0]  # 木目は u(=x) 方向
baked = {}


def bake_one(mname, tile, res, normal, uv_span=None, rough=False):
    m = D.materials[mname]
    plane.data.materials.clear()
    plane.data.materials.append(m)
    plane.scale = (tile, tile, 1)
    span = uv_span or (1.0, 1.0)
    for lp, uv in zip(plane.data.uv_layers["UVMap"].data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp.uv = (uv[0] * span[0], uv[1] * span[1])
    for n in m.node_tree.nodes:
        if n.name == "dust_patch":
            n.inputs["To Max"].default_value = 0.0  # ほこりは縦の面にも出てしまうのでタイルには入れない
    for o in SC.objects:
        o.select_set(False)
    plane.select_set(True)
    bpy.context.view_layer.objects.active = plane
    out = {}
    for kind in (["color", "normal"] if normal else ["color"]) + (["rough"] if rough else []):
        img = D.images.new(f"bake_{mname}_{kind}", res, res, alpha=False)
        if kind in ("normal", "rough"):
            img.colorspace_settings.name = 'Non-Color'
        nd = m.node_tree.nodes.new("ShaderNodeTexImage")
        nd.image = img
        m.node_tree.nodes.active = nd
        if kind == "color":
            bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_clear=True)
        elif kind == "rough":
            bpy.ops.object.bake(type='ROUGHNESS', use_clear=True)
        else:
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', use_clear=True)
        m.node_tree.nodes.remove(nd)
        img.filepath_raw = os.path.join(TEXOUT, f"{mname}_{kind}.png")
        img.file_format = 'PNG'
        img.save()
        out[kind] = img
    baked[mname] = out


for mname, (tile, res, normal) in BAKE.items():
    if mname in D.materials:
        bake_one(mname, tile, res, normal)
        print("baked", mname)
for mname, t in PBR.items():
    res = 2048 if mname in ("wood_walnut", "floor_oak") else 1024
    bake_one(mname, 1.0, res, True, uv_span=t, rough=True)
    print("baked pbr", mname)
D.objects.remove(plane, do_unlink=True)


# ---------------- 1b. カーテン(ゲーム用に追加。dorm_room.blend には入れない) ----------------
def make_curtain(name, x0, width, sign, y, ztop, zbot, mat):
    """原点を外側の端に置き、sign 方向へ広がるひだ付きのカーテン。Godot で幅を縮めて開閉する"""
    nx, nz = int(width / 0.012), 14
    rnd = random.Random(len(name))
    phase = rnd.uniform(0, 6)
    me = D.meshes.new(name)
    bm = bmesh.new()
    vs = []
    for i in range(nx + 1):
        u = i / nx
        row = []
        for j in range(nz + 1):
            v = j / nz
            amp = 0.028 * (1 + 0.35 * v) * (1 + 0.15 * math.sin(u * 23 + phase))
            yy = amp * math.sin(2 * math.pi * u * width / 0.11)
            row.append(bm.verts.new((sign * u * width, yy, -(ztop - zbot) * v)))
        vs.append(row)
    for i in range(nx):
        for j in range(nz):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = D.objects.new(name, me)
    D.collections["02_Window"].objects.link(o)
    o.location = (x0, y, ztop)
    me.materials.append(mat)
    md = o.modifiers.new("Solidify", 'SOLIDIFY')
    md.thickness = 0.004
    return o


cur_m = D.materials.new("curtain_linen")
cur_m.use_nodes = True
cur_m.diffuse_color = (0.50, 0.36, 0.17, 1)
CY, ZT, ZB = 4.86, 2.56, 0.98
make_curtain("Curtain_L", -1.12, 1.42, 1, CY, ZT, ZB, cur_m)
make_curtain("Curtain_R", 1.56, 1.32, -1, CY, ZT, ZB, cur_m)
rod_m = D.materials["metal_brass"]
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.011, radius2=0.011, depth=2.74)
me = D.meshes.new("Curtain_Rod")
bm.to_mesh(me)
bm.free()
rod = D.objects.new("Curtain_Rod", me)
D.collections["02_Window"].objects.link(rod)
rod.location = (0.22, CY, ZT + 0.03)
rod.rotation_euler = (0, math.radians(90), 0)
me.materials.append(rod_m)
for x in (-1.16, 1.57):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.022)
    me = D.meshes.new("Curtain_Finial")
    bm.to_mesh(me)
    bm.free()
    f = D.objects.new("Curtain_Finial", me)
    D.collections["02_Window"].objects.link(f)
    f.location = (x, CY, ZT + 0.03)
    me.materials.append(rod_m)

# ---------------- 2. メッシュに確定 ----------------
def bsdf_val(m, name, default):
    try:
        b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        s = b.inputs[name]
        return default if s.is_linked else (tuple(s.default_value) if hasattr(s.default_value, "__len__") else s.default_value)
    except (StopIteration, KeyError, AttributeError):
        return default


dg = bpy.context.evaluated_depsgraph_get()
for o in list(SC.objects):
    if o.type in ('CURVE', 'FONT'):  # 文字(番号札・EXIT)もメッシュにする
        mesh = D.meshes.new_from_object(o.evaluated_get(dg))
        n = D.objects.new(o.name + "_mesh", mesh)
        for c in o.users_collection:
            c.objects.link(n)
        n.matrix_world = o.matrix_world.copy()
        D.objects.remove(o, do_unlink=True)
# ゲーム用に布団の細分化を下げる(約35万→約9万三角形、しわの形は保つ)
for o in SC.objects:
    for md in o.modifiers:
        if md.type == 'SUBSURF' and o.name.startswith("Bed_Duvet"):
            md.levels = md.render_levels = 1
dg = bpy.context.evaluated_depsgraph_get()
for o in list(SC.objects):
    if o.type == 'MESH' and len(o.modifiers):
        mesh = D.meshes.new_from_object(o.evaluated_get(dg))
        o.modifiers.clear()
        o.data = mesh

# ---------------- 3. UV ----------------
def mat_tile(m):
    if m and m.name == "curtain_linen":
        return 0.25
    if m and m.name in BAKE:
        return BAKE[m.name][0]
    return 1.0


for o in SC.objects:
    if o.type != 'MESH' or not o.data.polygons or o in PH_OBJS:
        continue
    me = o.data
    if me.uv_layers.get("UVMap") and any(m and m.name in PBR for m in me.materials):
        uvl = me.uv_layers["UVMap"]
        for p in me.polygons:
            m = me.materials[p.material_index] if p.material_index < len(me.materials) else None
            t = PBR.get(m.name) if m else None
            if t:
                for li in p.loop_indices:
                    u, v = uvl.data[li].uv
                    uvl.data[li].uv = (u / t[0], v / t[1])
        continue
    bm = bmesh.new()
    bm.from_mesh(me)
    for l in list(bm.loops.layers.uv):
        bm.loops.layers.uv.remove(l)
    uv = bm.loops.layers.uv.new("UVMap")
    co = [v.co for v in bm.verts]
    lo = Vector([min(c[i] for c in co) for i in range(3)])
    hi = Vector([max(c[i] for c in co) for i in range(3)])
    size = Vector([max(hi[i] - lo[i], 1e-6) for i in range(3)])
    grain = max(range(3), key=lambda i: size[i])
    for f in bm.faces:
        m = me.materials[f.material_index] if f.material_index < len(me.materials) else None
        name = m.name if m else ""
        if name in IMAGE_MATS:
            a, b = ("XYZ".index(IMAGE_MATS[name][0]), "XYZ".index(IMAGE_MATS[name][1]))
            for lp in f.loops:
                c = lp.vert.co
                lp[uv].uv = ((c[a] - lo[a]) / size[a], (c[b] - lo[b]) / size[b])
            continue
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [i for i in range(3) if i != ax]
        if name == "floor_oak":
            a, b = 0, 1  # 板は v(=y) 方向
        elif grain in (a, b) and grain != a:
            a, b = b, a  # 木目(最長辺)を u に
        t = mat_tile(m)
        sx = o.matrix_world.to_scale()
        for lp in f.loops:
            c = lp.vert.co
            lp[uv].uv = (c[a] * sx[a] / t, c[b] * sx[b] / t)
    bm.to_mesh(me)
    bm.free()


# ---------------- 4. マテリアルの置き換え ----------------
def new_pbr(name, color=(0.5, 0.5, 0.5), rough=0.6, metal=0.0, img=None, nrm=None, emit_img=None, emit_col=None,
            emit=0.0, alpha=1.0, rough_img=None):
    m = D.materials.new("gd_" + name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color[:3], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if img:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    if rough_img:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = rough_img
        sp = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], sp.inputs["Color"])
        nt.links.new(sp.outputs["Green"], b.inputs["Roughness"])
    if nrm:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = nrm
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if emit_img:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = emit_img
        nt.links.new(t.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    elif emit_col:
        b.inputs["Emission Color"].default_value = (*emit_col, 1)
        b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except AttributeError:
            pass
    return m


def image_of(m):
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and not n.image.name.endswith("_bump"):
            return n.image
    return None


rep = {}
leaf_vars = [new_pbr(f"leaf_{i}", c, 0.45) for i, c in enumerate([(0.04, 0.11, 0.03), (0.06, 0.16, 0.035), (0.10, 0.20, 0.05)])]
for m in list(D.materials):
    if m.name.startswith(("gd_", "bake_")) or not m.use_nodes or m.name in PH_MATS:
        continue
    col = tuple(m.diffuse_color)[:3]
    rough = bsdf_val(m, "Roughness", 0.6)
    rough = rough if isinstance(rough, float) else 0.6
    metal = bsdf_val(m, "Metallic", 0.0)
    metal = metal if isinstance(metal, float) else 0.0
    if m.name in baked:
        bk = baked[m.name]
        rep[m.name] = new_pbr(m.name, (1, 1, 1), rough, metal, bk["color"], bk.get("normal"), rough_img=bk.get("rough"))
    elif m.name == "fishbowl_bowl_glass":
        rep[m.name] = new_pbr(m.name, (0.88, 0.95, 0.95), 0.03, 0, alpha=0.14)
    elif m.name == "fishbowl_water":
        rep[m.name] = new_pbr(m.name, (0.50, 0.70, 0.68), 0.04, 0, alpha=0.30)
    elif m.name in ("hall_light_panel", "exit_sign_glow", "hall_screen_green", "fairy_bulb", "laptop_screen"):
        rep[m.name] = new_pbr(m.name, col, 0.3, 0, emit_col=col, emit={"hall_light_panel": 3.0, "exit_sign_glow": 4.0, "fairy_bulb": 5.0}.get(m.name, 1.2))
    elif m.name in ("pendant_opal_glass", "pendant_bulb"):
        rep[m.name] = new_pbr(m.name, col, 0.3, 0)  # 発光は Godot で点灯時だけ
    elif m.name == "frame_glass":
        rep[m.name] = new_pbr(m.name, (0.9, 0.93, 0.93), 0.04, 0, alpha=0.06)
    elif m.name == "curtain_linen":
        rep[m.name] = new_pbr(m.name, col, 0.85, 0, None, baked["fabric_sheet_white"].get("normal"))
    elif m.name == "night_campus":
        rep[m.name] = new_pbr(m.name, (0, 0, 0), 1.0, 0, None, None, image_of(m), emit=1.0)
    elif m.name == "monitor_screen":
        rep[m.name] = new_pbr(m.name, (0.05, 0.05, 0.05), 0.2, 0, image_of(m), None, image_of(m), emit=1.4)
    elif m.name in IMAGE_MATS and image_of(m):
        rep[m.name] = new_pbr(m.name, (1, 1, 1), rough, 0, image_of(m))
    elif m.name in ("lamp_globe_glass", "lamp_bulb"):
        rep[m.name] = new_pbr(m.name, col, 0.4, 0, emit_col=(1.0, 0.68, 0.38), emit=6.0 if "globe" in m.name else 12.0)
    elif m.name == "window_glass":
        rep[m.name] = new_pbr(m.name, (0.85, 0.9, 0.95), 0.05, 0, alpha=0.08)
    elif m.name == "metal_brass":
        rep[m.name] = new_pbr(m.name, (0.80, 0.58, 0.26), 0.3, 1.0)
    elif m.name == "metal_aluminum":
        rep[m.name] = new_pbr(m.name, (0.7, 0.7, 0.72), 0.3, 1.0)
    else:
        rep[m.name] = new_pbr(m.name, col, rough, metal)

for o in SC.objects:
    if o.type != 'MESH':
        continue
    for s in o.material_slots:
        if not s.material:
            continue
        if s.material.name == "leaf_green":
            s.material = random.choice(leaf_vars)
        elif s.material.name in rep:
            s.material = rep[s.material.name]

# ---------------- 書き出し ----------------
glb = os.path.join(OUT, "assets", "room.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', export_apply=True, export_lights=False,
                          export_cameras=False, export_yup=True, export_texcoords=True, export_normals=True,
                          export_materials='EXPORT', export_image_format='AUTO', export_animations=False)
print("exported", glb, round(os.path.getsize(glb) / 1e6, 1), "MB")


# ---------------- 5. Godot プロジェクト ----------------
def basis_from_dir(d, up=Vector((0, 1, 0))):
    z = -d.normalized()
    if abs(z.dot(up)) > 0.98:
        up = Vector((0, 0, 1))
    x = up.cross(z).normalized()
    y = z.cross(x).normalized()
    return x, y, z


def xf(pos, d=None, yaw=None):
    if d is not None:
        x, y, z = basis_from_dir(d)
    elif yaw is not None:
        c, s = math.cos(yaw), math.sin(yaw)
        x, y, z = Vector((c, 0, -s)), Vector((0, 1, 0)), Vector((s, 0, c))
    else:
        x, y, z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    # tscn の Transform3D は基底を「行」で書く: (x.x, y.x, z.x, x.y, y.y, z.y, x.z, y.z, z.z, 原点)
    nums = [x.x, y.x, z.x, x.y, y.y, z.y, x.z, y.z, z.z, *pos]
    return "Transform3D(" + ", ".join(f"{v:.5f}" for v in nums) + ")"


spawn = g(Vector((0.0, 0.75, 0.0)))
SKY_ROT = float(os.environ.get("DORM_SKY_ROT", "-1.0472"))   # 丘の上の教会が窓の正面に来る向き
SKY_ENERGY = float(os.environ.get("DORM_SKY_ENERGY", "0.6"))
FOG = float(os.environ.get("DORM_FOG", "0.05"))
os.makedirs(os.path.join(OUT, "assets", "sky"), exist_ok=True)
import shutil
shutil.copy(os.path.join(ROOT, "assets_polyhaven", "hdri", "laufenurg_church_4k.hdr"), os.path.join(OUT, "assets", "sky", "laufenurg_church_4k.hdr"))
tscn = f'''[gd_scene load_steps=7 format=3]

[ext_resource type="PackedScene" path="res://assets/room.glb" id="1_room"]
[ext_resource type="Script" path="res://scripts/player.gd" id="2_player"]
[ext_resource type="Script" path="res://scripts/room_setup.gd" id="3_setup"]
[ext_resource type="Texture2D" path="res://assets/sky/laufenurg_church_4k.hdr" id="4_sky"]

[sub_resource type="PanoramaSkyMaterial" id="PanoramaSkyMaterial_night"]
panorama = ExtResource("4_sky")
energy_multiplier = {SKY_ENERGY}

[sub_resource type="Sky" id="Sky_night"]
sky_material = SubResource("PanoramaSkyMaterial_night")

[sub_resource type="Environment" id="Environment_night"]
background_mode = 2
sky = SubResource("Sky_night")
sky_rotation = Vector3(0, {SKY_ROT}, 0)
ambient_light_source = 2
ambient_light_color = Color(0.32, 0.27, 0.24, 1)
ambient_light_energy = 0.2
tonemap_mode = 4
tonemap_exposure = 1.1
ssao_enabled = true
ssao_radius = 0.6
ssao_intensity = 1.6
sdfgi_enabled = true
sdfgi_use_occlusion = true
sdfgi_cascades = 2
sdfgi_min_cell_size = 0.05
sdfgi_energy = 1.6
glow_enabled = true
glow_intensity = 0.5
glow_bloom = 0.04
ssr_enabled = true
ssr_max_steps = 48
ssr_fade_in = 0.2
ssr_depth_tolerance = 0.12
ssil_enabled = true
ssil_radius = 2.0
ssil_intensity = 0.8
volumetric_fog_enabled = true
volumetric_fog_density = {FOG}
volumetric_fog_albedo = Color(0.92, 0.9, 0.86, 1)
volumetric_fog_anisotropy = 0.55
volumetric_fog_length = 9.0
volumetric_fog_detail_spread = 1.5
volumetric_fog_ambient_inject = 0.0
volumetric_fog_sky_affect = 0.0

[sub_resource type="CapsuleShape3D" id="CapsuleShape3D_player"]
radius = 0.22
height = 1.6

[node name="Main" type="Node3D"]
script = ExtResource("3_setup")

[node name="WorldEnvironment" type="WorldEnvironment" parent="."]
environment = SubResource("Environment_night")

[node name="Room" parent="." instance=ExtResource("1_room")]

[node name="DeskLamp" type="SpotLight3D" parent="."]
transform = {xf(LI["lamp"]["pos"], LI["lamp"]["dir"])}
light_color = Color(1, 0.62, 0.32, 1)
light_energy = 4.0
shadow_enabled = true
spot_range = 3.5
spot_attenuation = 1.2
spot_angle = 48.0
spot_angle_attenuation = 1.6
light_volumetric_fog_energy = 5.0

[node name="DeskLampGlow" type="OmniLight3D" parent="."]
transform = {xf(LI["lamp"]["pos"])}
light_color = Color(1, 0.62, 0.32, 1)
light_energy = 0.35
omni_range = 1.4
light_volumetric_fog_energy = 0.5

[node name="GlobeLamp" type="OmniLight3D" parent="."]
transform = {xf(LI["globe"]["pos"])}
light_color = Color(1, 0.66, 0.36, 1)
light_energy = 0.9
shadow_enabled = true
omni_range = 2.4
omni_attenuation = 1.8
light_volumetric_fog_energy = 1.5

[node name="MonitorLight" type="SpotLight3D" parent="."]
transform = {xf(LI["monitor"]["pos"] + LI["monitor"]["dir"] * 0.05, LI["monitor"]["dir"])}
light_color = Color(0.75, 0.82, 0.95, 1)
light_energy = 0.8
spot_range = 2.2
spot_angle = 70.0
light_volumetric_fog_energy = 0.6

[node name="Moon" type="DirectionalLight3D" parent="."]
transform = {xf(Vector((0, 4, -6)), LI["moon"]["dir"])}
light_color = Color(0.58, 0.7, 1, 1)
light_energy = 0.55
shadow_enabled = true
directional_shadow_max_distance = 15.0
light_volumetric_fog_energy = 12.0

[node name="WindowSky" type="SpotLight3D" parent="."]
transform = {xf(LI["window"]["pos"], LI["window"]["dir"])}
light_color = Color(0.42, 0.52, 0.85, 1)
light_energy = 0.7
spot_range = 6.0
spot_angle = 80.0
light_volumetric_fog_energy = 0.4

[node name="WarmBounce" type="OmniLight3D" parent="."]
transform = {xf(LI["bounce"]["pos"] + Vector((0, -0.4, 0)))}
light_color = Color(1, 0.7, 0.45, 1)
light_energy = 0.4
omni_range = 5.0
light_volumetric_fog_energy = 0.0

[node name="Player" type="CharacterBody3D" parent="."]
transform = {xf(spawn, yaw=math.radians(21.5))}
script = ExtResource("2_player")

[node name="Collision" type="CollisionShape3D" parent="Player"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.8, 0)
shape = SubResource("CapsuleShape3D_player")

[node name="Head" type="Node3D" parent="Player"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1.5, 0)

[node name="Camera3D" type="Camera3D" parent="Player/Head"]
fov = 68.0
near = 0.03

[node name="RecordPlayer" type="AudioStreamPlayer3D" parent="."]
unit_size = 2.5
max_distance = 14.0
volume_db = -3.0

[node name="HUD" type="CanvasLayer" parent="."]

[node name="Help" type="Label" parent="HUD"]
offset_left = 16.0
offset_top = 12.0
offset_right = 1100.0
offset_bottom = 40.0
theme_override_colors/font_color = Color(1, 1, 1, 0.75)
text = "WASD: 移動 / Shift: 速く歩く / Space: ジャンプ / E: 調べる・使う / F: 集中モード / T: 昼と夜 / Tab: 今日のこと / P: 写真 / Esc: カーソル解除"

[node name="Prompt" type="Label" parent="HUD"]
anchors_preset = 7
anchor_left = 0.5
anchor_top = 1.0
anchor_right = 0.5
anchor_bottom = 1.0
offset_left = -200.0
offset_top = -90.0
offset_right = 200.0
offset_bottom = -56.0
grow_horizontal = 2
grow_vertical = 0
theme_override_colors/font_color = Color(1, 1, 1, 0.9)
theme_override_colors/font_outline_color = Color(0, 0, 0, 0.6)
theme_override_constants/outline_size = 4
theme_override_font_sizes/font_size = 22
horizontal_alignment = 1
'''
open(os.path.join(OUT, "main.tscn"), "w", encoding="utf-8").write(tscn)

open(os.path.join(OUT, "project.godot"), "w", encoding="utf-8").write('''; Godot プロジェクト設定
config_version=5

[application]

config/name="Dorm Room Walk"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.7", "Forward Plus")

[display]

window/size/viewport_width=1536
window/size/viewport_height=1024
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"

[rendering]

anti_aliasing/quality/msaa_3d=2
anti_aliasing/quality/use_taa=true
lights_and_shadows/positional_shadow/soft_shadow_filter_quality=3
global_illumination/voxel_gi/quality=0
lights_and_shadows/directional_shadow/soft_shadow_filter_quality=3
''')

import shutil
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "player.gd"), os.path.join(OUT, "scripts", "player.gd"))

shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "room_setup.gd"), os.path.join(OUT, "scripts", "room_setup.gd"))
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "focus_mode.gd"), os.path.join(OUT, "scripts", "focus_mode.gd"))
os.makedirs(os.path.join(OUT, "assets", "sounds"), exist_ok=True)
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "chime.wav"), os.path.join(OUT, "assets", "sounds", "chime.wav"))
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "life.gd"), os.path.join(OUT, "scripts", "life.gd"))
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "world.gd"), os.path.join(OUT, "scripts", "world.gd"))
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "dorm.gd"), os.path.join(OUT, "scripts", "dorm.gd"))
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "visuals.gd"), os.path.join(OUT, "scripts", "visuals.gd"))
for _i in range(4):
    shutil.copy(os.path.join(ROOT, "scripts", "godot_src", f"step_{_i}.wav"), os.path.join(OUT, "assets", "sounds", f"step_{_i}.wav"))
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "knock.wav"), os.path.join(OUT, "assets", "sounds", "knock.wav"))
os.makedirs(os.path.join(OUT, "assets", "tv"), exist_ok=True)
for _f in os.listdir(os.path.join(ROOT, "textures", "real_photos")):  # ラウンジのテレビのスライドショー
    shutil.copy(os.path.join(ROOT, "textures", "real_photos", _f), os.path.join(OUT, "assets", "tv", _f))
shutil.copy(os.path.join(ROOT, "assets_polyhaven", "photos", "cambridge.jpg"), os.path.join(OUT, "assets", "sky", "cambridge.jpg"))
shutil.copy(os.path.join(ROOT, "scripts", "godot_src", "rain.wav"), os.path.join(OUT, "assets", "sounds", "rain.wav"))
print("godot project written", OUT, "spawn", tuple(round(v, 2) for v in spawn))
