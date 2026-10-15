"""リアル版 段階R7: 入れる隣の部屋(315)、共用ラウンジ、シャワールーム。r6_hallway.py の後に Blender 内で exec する。
名前の先頭(R315_ / Lounge_ / Shower_)は Godot 側の dorm.gd と対応させている。
座標: 315 号室 x 1.72..5.20 / y 0.35..4.60、ラウンジ x 1.30..6.90 / y -6.20..-1.72、
シャワールーム x -6.88..-4.10 / y -5.40..-1.72(いずれも内側)。"""
import bpy, bmesh, os, math, random
from mathutils import Vector

ROOT = os.path.dirname(bpy.data.filepath)
exec(open(os.path.join(ROOT, "scripts", "helpers.py")).read())
_r1 = {}
exec(open(os.path.join(ROOT, "scripts", "r1_pbr.py")).read().split("# ---------------- 実行 ----------------")[0], _r1)
build, uv_box, SPEC = _r1["build"], _r1["uv_box"], _r1["SPEC"]
random.seed(31)

rm("R315_", "Lounge_", "Shower_")
# 複製した植物の部品は名前に目印が付かないので、各空間のコレクションごと空にする
for cname in ("24_Room315", "25_Lounge", "26_Shower"):
    cc = D.collections.get(cname)
    if cc:
        for o in list(cc.objects):
            D.objects.remove(o, do_unlink=True)
for n in ("fabric_navy_duvet", "fabric_mustard", "lounge_sofa_fabric"):
    if n not in D.materials:
        D.materials.new(n)
    build(n, *SPEC[n])
M = D.materials
floor_m, wall_m, oak, ceil_m = M["floor_oak"], M["wall_plaster"], M["hall_door_oak"], M["hall_ceiling_tile"]
sheet, navy, mustard, sofa_m = M["fabric_sheet_white"], M["fabric_navy_duvet"], M["fabric_mustard"], M["lounge_sofa_fabric"]
glass_m, bronze, light_m = M["frame_glass"], M["window_frame_bronze"], M["hall_light_panel"]
steel, blackp, white_p = M["metal_steel_brushed"], M["plastic_black"], M["plastic_white_outlet"]
laminate = mat("laminate_white", (0.82, 0.81, 0.78), 0.35)
counter_m = mat("counter_dark", (0.10, 0.10, 0.11), 0.25)
partition_m = mat("partition_gray", (0.42, 0.44, 0.45), 0.35)
mirror_m = mat("mirror_silver", (0.92, 0.92, 0.92), 0.02, 1.0)
porcelain = mat("porcelain_white", (0.90, 0.90, 0.88), 0.08)
curtain_m = mat("shower_curtain_white", (0.82, 0.84, 0.85), 0.5)
towel_m = mat("towel_teal", (0.15, 0.40, 0.42), 0.95)
fairy_m = mat("fairy_bulb", (1.0, 0.85, 0.55), 0.3, 0, ((1.0, 0.72, 0.38), 6.0))
laptop_m = mat("laptop_screen", (0.06, 0.08, 0.10), 0.15, 0, ((0.45, 0.6, 0.85), 1.2))
tv_m = mat("tv_screen", (0.02, 0.02, 0.025), 0.12)
pennant_m = mat("pennant_maroon", (0.38, 0.05, 0.08), 0.9)


def tile_mat(name, base, grout, size, gap):
    """正方形タイル(書き出し時にベイクする)"""
    m = M.get(name) or M.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0  # 既定の 5 のままだとタイルが 1/5 の大きさになる
    br.inputs["Brick Width"].default_value = size
    br.inputs["Row Height"].default_value = size
    br.inputs["Mortar Size"].default_value = gap
    br.inputs["Color1"].default_value = (*base, 1)
    br.inputs["Color2"].default_value = (*[c * 0.97 for c in base], 1)
    br.inputs["Mortar"].default_value = (*grout, 1)
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.18
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.002
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(br.outputs["Fac"], inv.inputs[1])
    nt.links.new(inv.outputs[0], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs[0], o.inputs["Surface"])
    m.diffuse_color = (*base, 1)
    return m


def image_mat(name, path, axes=("X", "Z")):
    m = M.get(name) or M.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs[axes[0]], comb.inputs["X"])
    nt.links.new(sep.outputs[axes[1]], comb.inputs["Y"])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = D.images.load(bpy.path.relpath(path), check_existing=True)
    nt.links.new(comb.outputs["Vector"], t.inputs["Vector"])
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.65
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs[0], o.inputs["Surface"])
    return m


# 目地の幅(メートル)は 5〜6mm
tile_wall = tile_mat("tile_wall_white", (0.86, 0.87, 0.86), (0.62, 0.63, 0.62), 0.15, 0.006)
tile_floor = tile_mat("tile_floor_gray", (0.36, 0.38, 0.39), (0.24, 0.24, 0.24), 0.10, 0.005)
HALL_TEX = os.path.join(ROOT, "textures", "hall")


def room_shell(prefix, c, x0, x1, y0, y1, ceil_z, wall, floor, windows=(), skip=(), window_wall="back"):
    """内側 x0..x1 / y0..y1 の部屋の床・天井・壁。windows は (x_a, x_b, z_a, z_b)。skip は作らない壁の名前"""
    T = 0.12
    box(f"{prefix}_Floor", (x0 - T, y0 - T, -0.1), (x1 + T, y1 + T, 0.0), c, floor)
    box(f"{prefix}_Ceiling", (x0 - T, y0 - T, ceil_z), (x1 + T, y1 + T, ceil_z + 0.1), c, ceil_m)
    if "left" not in skip:
        box(f"{prefix}_WallL", (x0 - T, y0 - T, 0), (x0, y1 + T, ceil_z), c, wall)
    if "right" not in skip:
        box(f"{prefix}_WallR", (x1, y0 - T, 0), (x1 + T, y1 + T, ceil_z), c, wall)
    # 窓のある壁: back は y1 側、front は y0 側
    wy0, wy1 = (y1, y1 + T) if window_wall == "back" else (y0 - T, y0)
    xs = x0 - T
    for i, (a, b, za, zb) in enumerate(windows):
        box(f"{prefix}_WallW_{i}a", (xs, wy0, 0), (a, wy1, ceil_z), c, wall)
        box(f"{prefix}_WallW_{i}low", (a, wy0, 0), (b, wy1, za), c, wall)
        box(f"{prefix}_WallW_{i}high", (a, wy0, zb), (b, wy1, ceil_z), c, wall)
        gy = wy1 - 0.03 if window_wall == "back" else wy0 + 0.03
        box(f"{prefix}_Glass_{i}", (a, gy - 0.003, za), (b, gy + 0.003, zb), c, glass_m)
        for fn, lo, hi in [("B", (a, gy - 0.025, za), (b, gy + 0.025, za + 0.05)), ("T", (a, gy - 0.025, zb - 0.05), (b, gy + 0.025, zb)),
                           ("L", (a, gy - 0.025, za), (a + 0.05, gy + 0.025, zb)), ("R", (b - 0.05, gy - 0.025, za), (b, gy + 0.025, zb))]:
            box(f"{prefix}_WinFrame_{i}{fn}", lo, hi, c, bronze)
        sy0, sy1 = (wy0 - 0.08, wy0 + 0.02) if window_wall == "back" else (wy1 - 0.02, wy1 + 0.08)
        box(f"{prefix}_Sill_{i}", (a - 0.03, sy0, za - 0.03), (b + 0.03, sy1, za), c, white_p)
        xs = b
    if windows or window_wall:
        box(f"{prefix}_WallW_end", (xs, wy0, 0), (x1 + T, wy1, ceil_z), c, wall)


def soft(n, lo, hi, c, m, bv=0.05):
    o = box(n, lo, hi, c, m, bv, 4)
    return o


def duvet(n, x0, x1, y0, y1, z, c, m):
    """マットレスにかけた布団(上面のふくらみ + 両脇の垂れ)"""
    soft(n + "_Top", (x0 - 0.03, y0, z), (x1 + 0.03, y1, z + 0.12), c, m, 0.06)
    soft(n + "_SideL", (x0 - 0.06, y0, z - 0.30), (x0 + 0.02, y1, z + 0.08), c, m, 0.035)
    soft(n + "_SideR", (x1 - 0.02, y0, z - 0.30), (x1 + 0.06, y1, z + 0.08), c, m, 0.035)
    soft(n + "_Foot", (x0 - 0.03, y0 - 0.06, z - 0.28), (x1 + 0.03, y0 + 0.02, z + 0.08), c, m, 0.035)


def chair_simple(n, loc, rotz, c):
    """寮の机の椅子(木の座面と背もたれ、スチールの脚)"""
    parts = [box(n + "_Seat", (-0.21, -0.21, 0.43), (0.21, 0.21, 0.46), c, oak, 0.01),
             box(n + "_Back", (0.17, -0.20, 0.62), (0.20, 0.20, 0.88), c, oak, 0.01)]
    for sx in (-0.18, 0.18):
        for sy in (-0.18, 0.18):
            parts.append(cyl(n + "_Leg", (sx, sy, 0), (sx, sy, 0.43), 0.011, 0.011, c, steel, 10))
    for sy in (-0.17, 0.17):
        parts.append(cyl(n + "_Upright", (0.185, sy, 0.43), (0.185, sy, 0.80), 0.01, 0.01, c, steel, 10))
    return group(n, parts, c, loc, rotz)


def desk(n, x0, x1, y0, y1, c):
    box(n + "_Top", (x0, y0, 0.73), (x1, y1, 0.76), c, oak, 0.004)
    box(n + "_PanelL", (x0, y0, 0), (x0 + 0.02, y1, 0.73), c, laminate)
    box(n + "_PanelR", (x1 - 0.02, y0, 0), (x1, y1, 0.73), c, laminate)
    box(n + "_Drawers", (x1 - 0.42, y0 + 0.02, 0.05), (x1 - 0.02, y1 - 0.02, 0.70), c, laminate, 0.004)
    for i in range(3):
        z = 0.08 + i * 0.21
        box(n + f"_Pull{i}", (x1 - 0.30, y0 - 0.005, z + 0.15), (x1 - 0.14, y0 + 0.02, z + 0.165), c, steel, 0.003)


def laptop(n, x, y, rotz, c, open_=True):
    parts = [box(n + "_Base", (-0.16, -0.11, 0), (0.16, 0.11, 0.015), c, M["metal_aluminum"], 0.004)]
    if open_:
        lid = box(n + "_Lid", (-0.16, -0.004, 0), (0.16, 0.004, 0.21), c, M["metal_aluminum"], 0.003, at=(0, 0.11, 0.015), rot=(math.radians(-12), 0, 0))
        scr = box(n + "_Screen", (-0.145, -0.001, 0.012), (0.145, 0.0, 0.198), c, laptop_m, at=(0, 0.105, 0.015), rot=(math.radians(-12), 0, 0))
        parts += [lid, scr]
    return group(n, parts, c, (x, y, 0.76), rotz)


def copy_tree(src_name, new_name, loc, scale=1.0, rotz=0.0, c=None):
    """Poly Haven の植物などを、メッシュを共有したまま複製する"""
    src = D.objects.get(src_name)
    if src is None:
        return None
    e = D.objects.new(new_name, None)
    (c or src.users_collection[0]).objects.link(e)

    def rec(o, parent):
        d = o.copy()
        (c or o.users_collection[0]).objects.link(d)
        d.parent = parent
        d.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        d.matrix_basis = o.matrix_basis.copy()
        for ch in o.children:
            rec(ch, d)

    rec(src, e)
    root = e.children[0]
    root.location = (0, 0, 0)
    e.location = loc
    e.scale = (scale, scale, scale)
    e.rotation_euler.z = rotz
    return e


# ================= 315 号室 =================
R = coll("24_Room315")
X0, X1, Y0, Y1 = 1.72, 5.20, 0.35, 4.60
room_shell("R315", R, X0, X1, Y0, Y1, 2.70, wall_m, floor_m, windows=[(2.65, 4.25, 0.95, 2.25)], skip=("left",))
# 巾木はドアの開口(x 2.94..3.86)を空ける(段差になって入れなくなるため)
for bx0, bx1 in ((X0, 2.94), (3.86, X1)):
    box("R315_Baseboard", (bx0, Y0, 0), (bx1, Y0 + 0.012, 0.09), R, white_p)
# ベッド 2 台(左は紺、右はからし色)
for i, (bx0, bx1, dm) in enumerate(((1.74, 2.74, navy), (4.18, 5.18, mustard))):
    by0, by1 = 2.50, 4.55
    box(f"R315_Bed{i}_Frame", (bx0, by0, 0.28), (bx1, by1, 0.40), R, oak, 0.006)
    for x in (bx0 + 0.04, bx1 - 0.08):
        for y in (by0 + 0.04, by1 - 0.08):
            box(f"R315_Bed{i}_Leg", (x, y, 0), (x + 0.04, y + 0.04, 0.28), R, oak)
    box(f"R315_Bed{i}_Mattress", (bx0 + 0.02, by0 + 0.02, 0.40), (bx1 - 0.02, by1 - 0.02, 0.58), R, sheet, 0.04, 3)
    duvet(f"R315_Bed{i}_Duvet", bx0, bx1, by0 - 0.02, by1 - 0.55, 0.52, R, dm)
    pillow(f"R315_Bed{i}_Pillow", 0.62, 0.40, 0.15, R, sheet, ((bx0 + bx1) / 2, by1 - 0.25, 0.68), (math.radians(20), 0, math.radians(90)), seed=40 + i)
box("R315_Bed0_Headboard", (1.74, 4.55, 0.28), (2.74, 4.59, 0.95), R, oak, 0.006)
box("R315_Bed1_Headboard", (4.18, 4.55, 0.28), (5.18, 4.59, 0.95), R, oak, 0.006)
# 机と椅子・ノートPC・小物
desk("R315_Desk0", 1.74, 2.80, 0.40, 1.05, R)
desk("R315_Desk1", 4.12, 5.18, 0.40, 1.05, R)
chair_simple("R315_Chair0", (2.27, 1.35, 0), math.radians(-95), R)
chair_simple("R315_Chair1", (4.65, 1.38, 0), math.radians(-80), R)
laptop("R315_Laptop0", 2.25, 0.70, math.radians(180), R, True)
laptop("R315_Laptop1", 4.70, 0.72, math.radians(185), R, False)
lathe("R315_Can", [(0.0005, 0), (0.033, 0), (0.033, 0.12), (0.028, 0.125), (0.0005, 0.125)], (2.62, 0.62, 0.76), R, mat("can_blue", (0.05, 0.25, 0.6), 0.3, 0.8))
lathe("R315_Mug", [(0.036, 0), (0.04, 0.09), (0.037, 0.09), (0.035, 0.008), (0.0005, 0.008)], (4.30, 0.62, 0.76), R, M["ceramic_dark"], cap=False)
tube("R315_Headphones", [(4.95, 0.62, 0.765), (4.95, 0.70, 0.84), (4.95, 0.82, 0.86), (4.95, 0.92, 0.80), (4.95, 0.96, 0.765)], 0.012, R, blackp)
z = 0.76
for i in range(3):
    book(f"R315_Book{i}", R, book_mat(i + 4), (1.95, 0.85, z), (0.24, 0.17, 0.03), rotz=math.radians(random.uniform(-10, 10)))
    z += 0.03
# デスクライト(白い可動式)
cyl("R315_Lamp_Base", (1.92, 0.55, 0.76), (1.92, 0.55, 0.78), 0.07, 0.07, R, white_p, 20)
cyl("R315_Lamp_Arm", (1.92, 0.55, 0.78), (2.05, 0.62, 1.15), 0.008, 0.008, R, white_p, 10)
lathe("R315_Lamp_Shade", [(0.01, 0), (0.05, -0.03), (0.065, -0.09), (0.06, -0.09), (0.045, -0.03), (0.008, -0.003)], (2.06, 0.63, 1.16), R, white_p, cap=False)
# クローゼット 2 つ
for i, (wx0, wx1) in enumerate(((1.74, 2.38), (4.54, 5.18))):
    box(f"R315_Wardrobe{i}", (wx0, 1.62, 0), (wx1, 2.40, 1.95), R, laminate, 0.006)
    hx = wx1 + 0.012 if i == 0 else wx0 - 0.022
    box(f"R315_Wardrobe{i}_Handle", (hx, 1.95, 0.95), (hx + 0.01, 2.07, 1.05), R, steel, 0.003)
# ラグ・ミニ冷蔵庫・洗濯かご
r = box("R315_Rug", (2.90, 1.45, 0), (4.05, 3.85, 0.012), R, M["fabric_gray_wool"], 0.004)
box("R315_Fridge", (3.20, 4.08, 0), (3.72, 4.56, 0.86), R, white_p, 0.015, 3)
box("R315_Fridge_Handle", (3.62, 4.06, 0.55), (3.66, 4.08, 0.78), R, steel, 0.004)
copy_tree("PH_SillPlant3", "R315_FridgePlant", (3.46, 4.32, 0.86), 1.0, 0.7, R)
lathe("R315_Hamper", [(0.0005, 0), (0.20, 0), (0.22, 0.45), (0.205, 0.45), (0.185, 0.02), (0.0005, 0.02)], (2.62, 2.15, 0), R, M["wateringcan_green"] if "wateringcan_green" in M else laminate, cap=False)
for i in range(4):
    p = pillow(f"R315_Laundry{i}", 0.30, 0.24, 0.07, R, [M["fabric_gray_wool"], navy, mustard, sheet][i],
               (2.62 + random.uniform(-0.06, 0.06), 2.15 + random.uniform(-0.06, 0.06), 0.40 + i * 0.03), (random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), random.uniform(0, 3)), seed=60 + i)
# ポスター(左の壁は +x 向き、右の壁は -x 向きで反転版)
box("R315_PosterL", (X0, 3.00, 1.15), (X0 + 0.004, 3.60, 2.01), R, image_mat("poster_band", os.path.join(HALL_TEX, "poster_band.png"), ("Y", "Z")))
box("R315_PosterR", (X1 - 0.004, 3.20, 1.15), (X1, 3.80, 2.01), R, image_mat("poster_film_m", os.path.join(HALL_TEX, "poster_film_m.png"), ("Y", "Z")))
# ペナント
bm = bmesh.new()
vs = [bm.verts.new(v) for v in ((0, 0, 0.13), (0, 0, -0.13), (0, 0.62, 0.0))]
bm.faces.new(vs)
pn = _finish("R315_Pennant", bm, R, pennant_m, loc=(X0 + 0.006, 3.70, 2.15))
solidify(pn, 0.003)
t = D.curves.new("R315_PennantText", 'FONT')
t.body = "OWLS"
t.size = 0.09
t.align_x = 'CENTER'
t.align_y = 'CENTER'
to = D.objects.new("R315_PennantText", t)
R.objects.link(to)
to.location = (X0 + 0.011, 3.92, 2.15)
to.rotation_euler = (math.radians(90), 0, math.radians(90))
t.materials.append(M["hall_plate_text"])
# ガーランドライト(奥の壁の上と右のベッドの上)
pts = []
for i in range(15):
    u = i / 14
    pts.append((X0 + 0.25 + u * (X1 - X0 - 0.5), Y1 - 0.03, 2.42 - 0.12 * math.sin(math.pi * u)))
tube("R315_FairyWire", pts, 0.0025, R, M["plastic_black"], 2)
for i, p in enumerate(pts[1:-1]):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.018)
    _finish(f"R315_Fairy_{i}", bm, R, fairy_m, smooth=True, loc=(p[0], p[1] - 0.01, p[2] - 0.025))
# 天井の照明
cyl("R315_CeilingLight", (3.46, 2.45, 2.66), (3.46, 2.45, 2.70), 0.22, 0.20, R, M["pendant_opal_glass"], 32)
for o in R.objects:
    if o.type == 'MESH' and any(s.material and s.material.name in ("hall_door_oak", "fabric_navy_duvet", "fabric_mustard", "fabric_gray_wool", "floor_oak", "wall_plaster", "fabric_sheet_white") for s in o.material_slots):
        uv_box(o, floor=o.name.endswith("_Floor"))

# ================= 共用ラウンジ =================
L = coll("25_Lounge")
LX0, LX1, LY0, LY1 = 1.30, 6.90, -6.20, -1.72
room_shell("Lounge", L, LX0, LX1, LY0, LY1, 2.70, M["hall_wall_paint"], floor_m,
           windows=[(2.1, 3.7, 0.85, 2.35), (4.5, 6.1, 0.85, 2.35)], window_wall="front")
for i, x in enumerate((2.6, 4.1, 5.6)):
    box(f"Lounge_Light_{i}", (x - 0.6, -4.3, 2.685), (x + 0.6, -3.7, 2.70), L, light_m)
# L 字ソファ(テレビのある東の壁を向く)
sx0, sx1 = 3.55, 4.45
soft("Lounge_Sofa_Base", (sx0, -5.30, 0.08), (sx1, -2.90, 0.42), L, sofa_m, 0.05)
soft("Lounge_Sofa_Back", (sx0, -5.30, 0.30), (sx0 + 0.22, -2.90, 0.88), L, sofa_m, 0.07)
soft("Lounge_Sofa_ArmN", (sx0, -3.10, 0.30), (sx1, -2.90, 0.64), L, sofa_m, 0.06)
soft("Lounge_Sofa_Chaise", (sx1 - 0.02, -5.30, 0.08), (5.35, -4.45, 0.42), L, sofa_m, 0.05)
soft("Lounge_Sofa_BackS", (sx0, -5.30, 0.30), (5.35, -5.08, 0.80), L, sofa_m, 0.07)
for i, y in enumerate((-4.85, -4.10, -3.40)):
    soft(f"Lounge_Sofa_Cushion{i}", (sx0 + 0.20, y - 0.36, 0.42), (sx1 - 0.02, y + 0.36, 0.55), L, sofa_m, 0.06)
for x, y in ((sx0 + 0.06, -5.24), (sx0 + 0.06, -2.96), (5.29, -5.24), (5.29, -4.51), (sx1 - 0.06, -2.96)):
    cyl("Lounge_Sofa_Leg", (x, y, 0), (x, y, 0.08), 0.02, 0.025, L, M["wood_walnut"], 12)
pillow("Lounge_Sofa_Pillow0", 0.42, 0.42, 0.14, L, mustard, (sx0 + 0.30, -4.80, 0.66), (math.radians(70), 0, math.radians(-90)), seed=70)
pillow("Lounge_Sofa_Pillow1", 0.42, 0.42, 0.14, L, M["fabric_rust_velvet"], (sx0 + 0.30, -3.30, 0.66), (math.radians(68), 0, math.radians(-95)), seed=71)
# ローテーブル・テレビ・ラグ
box("Lounge_Table_Top", (4.85, -4.30, 0.38), (5.75, -3.40, 0.42), L, M["wood_walnut"], 0.006)
for x in (4.92, 5.68):
    for y in (-4.23, -3.47):
        cyl("Lounge_Table_Leg", (x, y, 0), (x, y, 0.38), 0.015, 0.02, L, M["wood_walnut"], 10)
box("Lounge_Rug", (3.40, -5.50, 0), (6.10, -2.70, 0.012), L, M["fabric_gray_wool"], 0.004)
box("Lounge_TV_Frame", (LX1 - 0.06, -4.55, 1.05), (LX1, -3.15, 1.85), L, blackp, 0.006)
box("Lounge_TV_Screen", (LX1 - 0.062, -4.52, 1.08), (LX1 - 0.058, -3.18, 1.82), L, tv_m)
box("Lounge_TV_Stand", (LX1 - 0.40, -4.40, 0), (LX1, -3.30, 0.48), L, M["wood_walnut_dark"], 0.006)
# キッチン(西の壁): 下の棚・カウンター・シンク・電子レンジ・吊り戸棚・冷蔵庫
kx0, kx1 = LX0, LX0 + 0.62
box("Lounge_Kitchen_Base", (kx0, -5.70, 0), (kx1, -3.40, 0.88), L, laminate, 0.004)
box("Lounge_Kitchen_Counter", (kx0, -5.72, 0.88), (kx1 + 0.03, -3.38, 0.92), L, counter_m, 0.004)
box("Lounge_Kitchen_Sink", (kx0 + 0.12, -5.20, 0.80), (kx1 - 0.10, -4.70, 0.921), L, steel, 0.01)
cyl("Lounge_Kitchen_Faucet", (kx0 + 0.08, -4.95, 0.92), (kx0 + 0.08, -4.95, 1.18), 0.012, 0.012, L, steel, 12)
cyl("Lounge_Kitchen_FaucetSpout", (kx0 + 0.08, -4.95, 1.18), (kx0 + 0.24, -4.95, 1.14), 0.01, 0.01, L, steel, 12)
box("Lounge_Microwave", (kx0 + 0.06, -4.20, 0.92), (kx0 + 0.46, -3.68, 1.22), L, M["metal_steel_brushed"], 0.01, 3)
box("Lounge_Microwave_Window", (kx0 + 0.461, -4.12, 0.98), (kx0 + 0.463, -3.86, 1.17), L, mat("microwave_glass", (0.02, 0.02, 0.02), 0.08))
box("Lounge_Microwave_Panel", (kx0 + 0.461, -3.83, 0.96), (kx0 + 0.463, -3.72, 1.19), L, blackp)
box("Lounge_Kitchen_Upper", (kx0, -5.70, 1.50), (kx0 + 0.35, -3.40, 2.20), L, laminate, 0.004)
for i, y in enumerate((-5.10, -4.00)):
    box(f"Lounge_Kitchen_Pull{i}", (kx1 - 0.005, y - 0.08, 0.72), (kx1 + 0.015, y + 0.08, 0.735), L, steel, 0.003)
box("Lounge_Fridge", (kx0, -3.30, 0), (kx0 + 0.70, -2.62, 1.80), L, M["metal_steel_brushed"], 0.015, 3)
box("Lounge_Fridge_Handle", (kx0 + 0.70, -2.75, 0.95), (kx0 + 0.725, -2.71, 1.55), L, blackp, 0.004)
# ダイニングテーブルと椅子(窓ぎわ)
box("Lounge_Dining_Top", (2.15, -5.95, 0.72), (3.15, -5.15, 0.75), L, oak, 0.006)
for x in (2.22, 3.08):
    for y in (-5.88, -5.22):
        cyl("Lounge_Dining_Leg", (x, y, 0), (x, y, 0.72), 0.018, 0.022, L, oak, 10)
for i, (x, y, rz) in enumerate(((2.40, -4.85, math.radians(90)), (2.90, -4.85, math.radians(90)), (2.40, -6.05, math.radians(-90)), (2.90, -6.05, math.radians(-90)))):
    chair_simple(f"Lounge_DiningChair{i}", (x, y, 0), rz, L)
# 本棚(ボードゲーム入り)と観葉植物、フロアランプ
box("Lounge_Shelf", (LX1 - 0.35, -2.60, 0), (LX1, -1.85, 1.50), L, oak, 0.004)
for i, z in enumerate((0.40, 0.80, 1.20)):
    box(f"Lounge_Shelf_Board{i}", (LX1 - 0.34, -2.59, z), (LX1 - 0.01, -1.86, z + 0.02), L, oak)
for i in range(6):
    w = random.uniform(0.25, 0.35)
    box(f"Lounge_Game{i}", (LX1 - 0.32, -2.55 + (i % 3) * 0.24, 0.02 + (i // 3) * 0.4 + 0.02),
        (LX1 - 0.04, -2.55 + (i % 3) * 0.24 + 0.22, 0.02 + (i // 3) * 0.4 + 0.02 + random.uniform(0.05, 0.08)), L, book_mat(i), 0.003)
copy_tree("PH_BigPlant", "Lounge_BigPlant", (6.45, -5.75, 0.258), 1.0, 0.4, L)  # 鉢の土の高さ(0.30×0.86)
copy_tree("PH_BigPlant_PotGroup", "Lounge_BigPlantPot", (6.45, -5.75, 0.0), 1.0, 0.0, L)
cyl("Lounge_FloorLamp_Base", (3.30, -5.55, 0), (3.30, -5.55, 0.03), 0.14, 0.14, L, M["metal_brass"], 24)
cyl("Lounge_FloorLamp_Pole", (3.30, -5.55, 0.03), (3.30, -5.55, 1.55), 0.012, 0.012, L, M["metal_brass"], 12)
lathe("Lounge_FloorLamp_Shade", [(0.14, 0), (0.17, 0.0), (0.12, 0.28), (0.09, 0.28)], (3.30, -5.55, 1.40), L, M["pendant_opal_glass"], cap=False)
for o in L.objects:
    if o.type == 'MESH' and any(s.material and s.material.name in SPEC for s in o.material_slots):
        uv_box(o, floor=o.name.endswith("_Floor"))

# ================= シャワールーム =================
S = coll("26_Shower")
SX0, SX1, SY0, SY1 = -6.88, -4.10, -5.40, -1.72
room_shell("Shower", S, SX0, SX1, SY0, SY1, 2.55, tile_wall, tile_floor, windows=(), window_wall="front")
for i, x in enumerate((-6.0, -4.9)):
    box(f"Shower_Light_{i}", (x - 0.3, -3.9, 2.535), (x + 0.3, -3.3, 2.55), S, light_m)
# 洗面台 2 つと大きな鏡(西の壁)
box("Shower_Counter", (SX0, -3.70, 0.82), (SX0 + 0.56, -1.95, 0.86), S, counter_m, 0.004)
box("Shower_CounterSkirt", (SX0, -3.70, 0.66), (SX0 + 0.56, -1.95, 0.82), S, laminate, 0.004)
for i, y in enumerate((-3.25, -2.40)):
    lathe(f"Shower_Basin{i}", [(0.0005, 0.0), (0.17, 0.0), (0.19, 0.04), (0.185, 0.045), (0.16, 0.01), (0.0005, 0.012)], (SX0 + 0.30, y, 0.86), S, porcelain, cap=False)
    cyl(f"Shower_Faucet{i}", (SX0 + 0.06, y, 0.86), (SX0 + 0.06, y, 1.05), 0.012, 0.012, S, steel, 12)
    cyl(f"Shower_FaucetSpout{i}", (SX0 + 0.06, y, 1.05), (SX0 + 0.20, y, 1.02), 0.009, 0.009, S, steel, 12)
box("Shower_Mirror", (SX0, -3.70, 1.05), (SX0 + 0.008, -1.95, 1.95), S, mirror_m)
box("Shower_MirrorFrame", (SX0, -3.72, 1.03), (SX0 + 0.006, -1.93, 1.97), S, steel, 0.002)
# シャワーブース 3 つ(奥の壁)、仕切り・カーテン・シャワーヘッド
stalls = [(-6.88, -5.98), (-5.98, -5.08), (-5.08, -4.18)]
for x in (-5.98, -5.08, -4.18):
    box("Shower_Partition", (x - 0.012, SY0, 0.10), (x + 0.012, -4.42, 2.05), S, partition_m, 0.004)
for i, (a, b) in enumerate(stalls):
    cx = (a + b) / 2
    cyl(f"Shower_Rod{i}", (a + 0.02, -4.42, 2.02), (b - 0.02, -4.42, 2.02), 0.008, 0.008, S, steel, 10)
    cyl(f"Shower_Arm{i}", (cx, SY0, 1.95), (cx, SY0 + 0.20, 1.92), 0.012, 0.012, S, steel, 12)
    cyl(f"Shower_Head{i}", (cx, SY0 + 0.20, 1.93), (cx, SY0 + 0.21, 1.90), 0.045, 0.06, S, steel, 24)
    cyl(f"Shower_Valve{i}", (cx, SY0, 1.15), (cx, SY0 + 0.05, 1.15), 0.035, 0.03, S, steel, 20)
    cyl(f"Shower_Drain{i}", (cx, -4.90, 0.0), (cx, -4.90, 0.003), 0.04, 0.04, S, steel, 16)
    # 片側に寄せたカーテン(ひだ)。開閉は Godot で幅を変える
    nx, nz = 40, 10
    width = (b - a) - 0.06
    bm = bmesh.new()
    grid = [[bm.verts.new((u / nx * width, 0.025 * math.sin(2 * math.pi * u / nx * width / 0.09), -1.75 * v / nz)) for v in range(nz + 1)] for u in range(nx + 1)]
    for u in range(nx):
        for v in range(nz):
            bm.faces.new((grid[u][v], grid[u + 1][v], grid[u + 1][v + 1], grid[u][v + 1]))
    cu = _finish(f"Shower_Curtain{i}", bm, S, curtain_m, smooth=True, loc=(a + 0.03, -4.42, 2.00))
    solidify(cu, 0.003)
    cu.scale.x = 0.3
# タオル掛けとタオル(東の壁)
cyl("Shower_TowelBar", (SX1 - 0.02, -3.10, 1.30), (SX1 - 0.02, -2.30, 1.30), 0.01, 0.01, S, steel, 10)
for i, y in enumerate((-2.95, -2.55)):
    soft(f"Shower_Towel{i}", (SX1 - 0.07, y - 0.18, 0.82), (SX1 - 0.02, y + 0.18, 1.32), S, [towel_m, M["fabric_sheet_white"]][i], 0.02)
print("spaces ok", len(R.objects), len(L.objects), len(S.objects))
