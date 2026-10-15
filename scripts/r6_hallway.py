"""リアル版 段階R6: ドアの先の、大学の寮の廊下。Blender 内で exec する。
座標: 部屋の入口の壁の廊下側は y=0.23。廊下は x -7..7、y -1.6..0.23、天井 2.55。
名前の先頭(Hall_ / Door_ など)は Godot 側の world.gd と対応させている。"""
import bpy, bmesh, os, math
from mathutils import Vector

ROOT = os.path.dirname(bpy.data.filepath)
exec(open(os.path.join(ROOT, "scripts", "helpers.py")).read())
_r1 = {}
exec(open(os.path.join(ROOT, "scripts", "r1_pbr.py")).read().split("# ---------------- 実行 ----------------")[0], _r1)
build, uv_box, SPEC = _r1["build"], _r1["uv_box"], _r1["SPEC"]

H = coll("23_Hallway")
rm("Hall_")
X0, X1, YN, YF, ZC = -7.0, 7.0, 0.23, -1.6, 2.55  # 端・端・自室側の壁面・向かいの壁面・天井
T = 0.12

for n in ("hall_carpet", "hall_wall_paint", "hall_door_oak"):
    if n not in D.materials:
        D.materials.new(n)
    build(n, *SPEC[n])
carpet, wall, oak = D.materials["hall_carpet"], D.materials["hall_wall_paint"], D.materials["hall_door_oak"]
frame_m = mat("hall_frame_metal", (0.48, 0.47, 0.44), 0.4, 0.35)
rubber = mat("hall_cove_rubber", (0.05, 0.05, 0.05), 0.6)
steel = mat("metal_steel_brushed")
white_p = mat("plastic_white_outlet")
plate_m = mat("hall_plate_dark", (0.06, 0.07, 0.08), 0.35)
text_m = mat("hall_plate_text", (0.85, 0.85, 0.82), 0.4)
red_m = mat("hall_extinguisher_red", (0.55, 0.03, 0.02), 0.25)
blue_m = mat("hall_recycle_blue", (0.05, 0.18, 0.45), 0.5)
gray_m = mat("hall_trash_gray", (0.18, 0.18, 0.18), 0.6)
light_m = mat("hall_light_panel", (0.95, 0.96, 0.97), 0.3, 0, ((0.95, 0.97, 1.0), 6.0))
exit_m = mat("exit_sign_glow", (0.9, 0.1, 0.05), 0.4, 0, ((1.0, 0.12, 0.05), 8.0))
glass_m = D.materials["frame_glass"]
bronze = D.materials["window_frame_bronze"]


def ceiling_tile_mat():
    """格子の吸音天井板(書き出し時にベイクする)"""
    m = D.materials.get("hall_ceiling_tile") or D.materials.new("hall_ceiling_tile")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.2
    br.inputs["Row Height"].default_value = 0.6
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Color1"].default_value = (0.80, 0.80, 0.78, 1)
    br.inputs["Color2"].default_value = (0.78, 0.78, 0.76, 1)
    br.inputs["Mortar"].default_value = (0.55, 0.55, 0.53, 1)
    nt.links.new(comb.outputs["Vector"], br.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 260.0
    nz.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    sk = lambda nd, i, o=False: next(x for x in (nd.outputs if o else nd.inputs) if x.identifier == i)
    sk(mix, "Factor_Float").default_value = 0.25
    nt.links.new(br.outputs["Color"], sk(mix, "A_Color"))
    nt.links.new(nz.outputs["Color"], sk(mix, "B_Color"))
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.95
    nt.links.new(sk(mix, "Result_Color", True), b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.5
    bp.inputs["Distance"].default_value = 0.002
    h = nt.nodes.new("ShaderNodeMath")
    h.operation = 'ADD'
    nt.links.new(br.outputs["Fac"], h.inputs[0])
    nt.links.new(nz.outputs["Fac"], h.inputs[1])
    nt.links.new(h.outputs[0], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs[0], o.inputs["Surface"])
    m.diffuse_color = (0.79, 0.79, 0.77, 1)
    return m


def image_mat(name, path):
    """Generated 座標(X 横・Z 縦)で貼る画像の素材"""
    m = D.materials.get(name) or D.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = D.images.load(bpy.path.relpath(path), check_existing=True)
    nt.links.new(comb.outputs["Vector"], t.inputs["Vector"])
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Roughness"].default_value = 0.6
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs[0], o.inputs["Surface"])
    m.diffuse_color = (0.9, 0.9, 0.88, 1)
    return m


def text(name, body, loc, size, facing, m, extrude=0.0015):
    """壁に貼った文字(facing='-y' は自室側の壁、'+y' は向かいの壁、'+x' は端の壁)"""
    cu = D.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    o = D.objects.new(name, cu)
    H.objects.link(o)
    o.location = loc
    rot = {"-y": (math.radians(90), 0, 0), "+y": (math.radians(90), 0, math.radians(180)),
           "+x": (math.radians(90), 0, math.radians(-90)), "-x": (math.radians(90), 0, math.radians(90))}[facing]
    o.rotation_euler = rot
    cu.materials.append(m)
    return o


tile_m = ceiling_tile_mat()

# ---- 床・壁・天井 ----
objs = []
objs.append(box("Hall_Floor", (X0, YF, 0.0), (X1, YN, 0.008), H, carpet))
# 向かいの壁: シャワールームのドア(x -5.86..-4.94)と、ラウンジの広い入口(x 2.3..4.3)を空ける
OPEN_SHOWER = (-5.86, -4.94, 2.10)
OPEN_LOUNGE = (2.30, 4.30, 2.30)
OPEN_315 = (2.94, 3.86, 2.10)   # 自室側の壁: 315 号室のドア


def wall_with_openings(name, x0, x1, y0, y1, openings):
    xs = x0
    for i, (a, b, h) in enumerate(sorted(openings)):
        objs.append(box(f"{name}_{i}a", (xs, y0, 0), (a, y1, 2.7), H, wall))
        objs.append(box(f"{name}_{i}top", (a, y0, h), (b, y1, 2.7), H, wall))
        xs = b
    objs.append(box(f"{name}_end", (xs, y0, 0), (x1, y1, 2.7), H, wall))


wall_with_openings("Hall_Wall_Far", X0 - T, X1 + T, YF - T, YF, [OPEN_SHOWER, OPEN_LOUNGE])
objs.append(box("Hall_Wall_NearL", (X0 - T, YN, 0), (-2.89, YN + T, 2.7), H, wall))
wall_with_openings("Hall_Wall_NearR", 1.72, X1 + T, YN, YN + T, [OPEN_315])
objs.append(box("Hall_Wall_EndW", (X0 - T, YF, 0), (X0, YN, 2.7), H, wall))
# 東の端: 窓(y -1.25..-0.15, z 0.9..2.2)
wy0, wy1, wz0, wz1 = -1.25, -0.15, 0.9, 2.2
for n, lo, hi in [("Below", (X1, YF, 0), (X1 + T, YN, wz0)), ("Above", (X1, YF, wz1), (X1 + T, YN, 2.7)),
                  ("Left", (X1, YF, wz0), (X1 + T, wy0, wz1)), ("Right", (X1, wy1, wz0), (X1 + T, YN, wz1))]:
    objs.append(box("Hall_Wall_EndE_" + n, lo, hi, H, wall))
box("Hall_Window_Glass", (X1 + 0.05, wy0, wz0), (X1 + 0.056, wy1, wz1), H, glass_m)
for n, lo, hi in [("B", (X1 + 0.03, wy0, wz0), (X1 + 0.08, wy1, wz0 + 0.05)), ("T", (X1 + 0.03, wy0, wz1 - 0.05), (X1 + 0.08, wy1, wz1)),
                  ("L", (X1 + 0.03, wy0, wz0), (X1 + 0.08, wy0 + 0.05, wz1)), ("R", (X1 + 0.03, wy1 - 0.05, wz0), (X1 + 0.08, wy1, wz1)),
                  ("M", (X1 + 0.03, (wy0 + wy1) / 2 - 0.025, wz0), (X1 + 0.08, (wy0 + wy1) / 2 + 0.025, wz1))]:
    box("Hall_Window_Frame" + n, lo, hi, H, bronze)
box("Hall_Window_Sill", (X1 - 0.12, wy0 - 0.03, wz0 - 0.03), (X1 + 0.05, wy1 + 0.03, wz0), H, white_p)
objs.append(box("Hall_Ceiling", (X0, YF, ZC), (X1, YN, ZC + 0.05), H, tile_m))
# 巾木(ゴムの立ち上がり)。自室のドア口(x -0.5..0.5)は空ける
for x0, x1 in ((X0, OPEN_SHOWER[0]), (OPEN_SHOWER[1], OPEN_LOUNGE[0]), (OPEN_LOUNGE[1], X1)):
    box("Hall_Cove_Far", (x0, YF, 0), (x1, YF + 0.012, 0.10), H, rubber)
for x0, x1 in ((X0, -0.5), (0.5, OPEN_315[0]), (OPEN_315[1], X1)):
    box("Hall_Cove_Near", (x0, YN - 0.012, 0), (x1, YN, 0.10), H, rubber)

# ---- 天井の蛍光灯パネル ----
for i, x in enumerate((-5.6, -3.2, -0.8, 1.6, 4.0, 6.2)):
    box(f"Hall_Light_{i}", (x - 0.6, -0.98, ZC - 0.015), (x + 0.6, -0.38, ZC), H, light_m)
    box(f"Hall_LightFrame_{i}", (x - 0.62, -1.0, ZC - 0.012), (x + 0.62, -0.36, ZC - 0.002), H, white_p)
for x in (-4.4, 2.8):
    cyl("Hall_Smoke", (x, -0.68, ZC - 0.03), (x, -0.68, ZC), 0.065, 0.06, H, white_p, 24)


# ---- ドア(番号札・レバー・ホワイトボード) ----
def door(n, x, side, number, board=None):
    wy = YN if side == "near" else YF
    face = "-y" if side == "near" else "+y"
    w, h = 0.92, 2.08
    out = []
    # 枠(金属)と扉(オーク)
    for fn, lo, hi in [("L", (x - w / 2 - 0.05, 0, 0), (x - w / 2, 0.03, h + 0.05)), ("R", (x + w / 2, 0, 0), (x + w / 2 + 0.05, 0.03, h + 0.05)),
                       ("T", (x - w / 2 - 0.05, 0, h), (x + w / 2 + 0.05, 0.03, h + 0.05))]:
        y0, y1 = sorted((wy, wy + (0.03 if side == "far" else -0.03)))
        out.append(box(f"Hall_Door{number}_Frame{fn}", (lo[0], y0, lo[2]), (hi[0], y1, hi[2]), H, frame_m, 0.003))
    y0, y1 = sorted((wy + (0.004 if side == "far" else -0.004), wy + (0.03 if side == "far" else -0.03)))
    out.append(box(f"Hall_Door{number}_Slab", (x - w / 2, y0, 0.01), (x + w / 2, y1, h), H, oak, 0.003))
    # レバーハンドル(戸先側)
    hx = x + w / 2 - 0.09
    yf = y1 if side == "far" else y0
    dy = 0.05 if side == "far" else -0.05
    out.append(cyl(f"Hall_Door{number}_Rose", (hx, yf, 1.0), (hx, yf + dy * 0.3, 1.0), 0.03, 0.03, H, steel, 20))
    out.append(cyl(f"Hall_Door{number}_LeverNeck", (hx, yf, 1.0), (hx, yf + dy, 1.0), 0.009, 0.009, H, steel, 12))
    out.append(cyl(f"Hall_Door{number}_Lever", (hx, yf + dy, 1.0), (hx - 0.12, yf + dy, 0.995), 0.01, 0.01, H, steel, 12))
    # 番号札(戸先側の壁)
    px = x + w / 2 + 0.22
    py0, py1 = sorted((wy, wy + (0.008 if side == "far" else -0.008)))
    pw = 0.08 if len(number) <= 3 else 0.024 * len(number)
    px = x + w / 2 + 0.06 + pw
    out.append(box(f"Hall_Door{number}_Plate", (px - pw, py0, 1.48), (px + pw, py1, 1.60), H, plate_m, 0.003))
    ty = py1 + 0.001 if side == "far" else py0 - 0.001
    out.append(text(f"Hall_Door{number}_Number", number, (px, ty, 1.54), 0.07 if len(number) <= 3 else 0.045, face, text_m))
    if board:
        by0, by1 = sorted((yf, yf + (0.006 if side == "far" else -0.006)))
        out.append(box(f"Hall_Door{number}_BoardFrame", (x - 0.22, by0, 1.30), (x + 0.22, by1, 1.62), H, frame_m, 0.002))
        bb0, bb1 = sorted((yf + (0.006 if side == "far" else -0.006), yf + (0.007 if side == "far" else -0.007)))
        out.append(box(f"Hall_Door{number}_Board", (x - 0.205, bb0, 1.315), (x + 0.205, bb1, 1.605), H,
                       image_mat(f"whiteboard_{board}" + ("_m" if side == "far" else ""), os.path.join(ROOT, "textures", "hall", f"whiteboard_{board}" + ("_m" if side == "far" else "") + ".png"))))
    return out


door("A", -4.8, "near", "311", 0)
door("B", 3.4, "near", "315", None)
door("C", -3.2, "far", "312", 1)
door("D", 0.8, "far", "314", None)
door("E", 6.0, "near", "317", 2)
door("S", -5.4, "far", "SHOWERS", None)   # シャワールーム(開くドア)
# 自分の部屋の番号札(ドアの右の壁)
box("Hall_MyDoor_Plate", (0.62 - 0.08, YN - 0.008, 1.48), (0.62 + 0.08, YN, 1.60), H, plate_m, 0.003)
text("Hall_MyDoor_Number", "313", (0.62, YN - 0.009, 1.54), 0.07, "-y", text_m)

# ---- 掲示板と貼り紙(自室側の壁、ドアの左) ----
cork = D.materials["cork_board"]
walnut = D.materials["wood_walnut"]
bx0, bx1, bz0, bz1 = -2.65, -1.35, 1.05, 1.85
box("Hall_Board_Cork", (bx0, YN - 0.015, bz0), (bx1, YN, bz1), H, cork)
for fn, lo, hi in [("B", (bx0 - 0.03, YN - 0.025, bz0 - 0.03), (bx1 + 0.03, YN, bz0)), ("T", (bx0 - 0.03, YN - 0.025, bz1), (bx1 + 0.03, YN, bz1 + 0.03)),
                   ("L", (bx0 - 0.03, YN - 0.025, bz0), (bx0, YN, bz1)), ("R", (bx1, YN - 0.025, bz0), (bx1 + 0.03, YN, bz1))]:
    box("Hall_Board_Frame" + fn, lo, hi, H, walnut, 0.003)
for i, (name, cx, cz, rot) in enumerate([("flyer_meeting", -2.42, 1.48, 3), ("flyer_study", -2.05, 1.42, -2), ("flyer_quiet", -1.68, 1.50, 1.5), ("flyer_soccer", -1.95, 1.62, -4)]):
    fw, fh = 0.21, 0.28
    o = box(f"Hall_Flyer_{i}", (-fw / 2, -0.001, -fh / 2), (fw / 2, 0.0, fh / 2), H,
            image_mat(name, os.path.join(ROOT, "textures", "hall", name + ".png")), at=(cx, YN - 0.016 - 0.001 * i, cz), rot=(0, math.radians(rot), 0))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.007)
    _finish(f"Hall_FlyerPin_{i}", bm, H, D.materials["pin_red"], smooth=True, loc=(cx, YN - 0.022 - 0.001 * i, cz + fh / 2 - 0.02))
text("Hall_Board_Title", "FLOOR 3 NEWS", (-2.0, YN - 0.016, 1.79), 0.05, "-y", plate_m)

# ---- 給水機(向かいの壁) ----
fx = -1.4
box("Hall_Fountain_Body", (fx - 0.24, YF, 0.72), (fx + 0.24, YF + 0.34, 0.98), H, steel, 0.02, 3)
box("Hall_Fountain_Basin", (fx - 0.19, YF + 0.06, 0.975), (fx + 0.19, YF + 0.30, 0.985), H, mat("hall_basin_dark", (0.2, 0.2, 0.21), 0.2, 0.8), 0.01)
cyl("Hall_Fountain_Spout", (fx, YF + 0.15, 0.985), (fx, YF + 0.15, 1.02), 0.012, 0.008, H, steel)
box("Hall_Fountain_BottleFiller", (fx - 0.17, YF, 1.10), (fx + 0.17, YF + 0.13, 1.55), H, steel, 0.015, 3)
box("Hall_Fountain_FillerScreen", (fx - 0.06, YF + 0.131, 1.46), (fx + 0.06, YF + 0.133, 1.51), H, mat("hall_screen_green", (0.05, 0.25, 0.1), 0.2, 0, ((0.2, 0.9, 0.4), 1.5)))

# ---- 消火器(向かいの壁) ----
ex = 5.3
lathe("Hall_Extinguisher", [(0.0005, 0.0), (0.075, 0.0), (0.08, 0.02), (0.08, 0.40), (0.06, 0.45), (0.025, 0.47), (0.0005, 0.47)],
      (ex, YF + 0.10, 0.55), H, red_m)
box("Hall_Extinguisher_Valve", (ex - 0.03, YF + 0.08, 1.02), (ex + 0.06, YF + 0.12, 1.06), H, mat("metal_aluminum"), 0.005)
box("Hall_Extinguisher_Bracket", (ex - 0.05, YF, 0.80), (ex + 0.05, YF + 0.03, 0.88), H, mat("plastic_black"))
box("Hall_Extinguisher_Sign", (ex - 0.13, YF, 1.35), (ex + 0.13, YF + 0.004, 1.52), H, red_m, 0.002)
text("Hall_Extinguisher_SignText", "FIRE\nEXTINGUISHER", (ex, YF + 0.0055, 1.435), 0.035, "+y", text_m)

# ---- ゴミ箱とリサイクル箱(向かいの壁ぎわ) ----
for n, x, m_, label in (("Trash", -0.45, gray_m, "TRASH"), ("Recycle", 0.05, blue_m, "RECYCLE")):
    box(f"Hall_{n}_Bin", (x - 0.2, YF + 0.02, 0), (x + 0.2, YF + 0.32, 0.72), H, m_, 0.02, 3)
    box(f"Hall_{n}_Lid", (x - 0.205, YF + 0.015, 0.72), (x + 0.205, YF + 0.325, 0.75), H, m_, 0.01, 3)
    text(f"Hall_{n}_Label", label, (x, YF + 0.322, 0.55), 0.045, "+y", text_m)

# ---- 西の端: 非常口と EXIT サイン ----
dx = X0
box("Hall_ExitDoor_Frame", (dx, -1.25, 0), (dx + 0.03, -0.15, 2.15), H, frame_m, 0.003)
box("Hall_ExitDoor_Slab", (dx + 0.03, -1.20, 0.01), (dx + 0.05, -0.20, 2.10), H, mat("hall_exit_door", (0.42, 0.42, 0.40), 0.4, 0.4), 0.003)
cyl("Hall_ExitDoor_PushBar", (dx + 0.10, -1.05, 1.0), (dx + 0.10, -0.35, 1.0), 0.02, 0.02, H, steel)
for y in (-1.05, -0.35):
    box("Hall_ExitDoor_BarMount", (dx + 0.05, y - 0.03, 0.97), (dx + 0.10, y + 0.03, 1.03), H, steel, 0.004)
box("Hall_Exit_Sign", (dx + 0.0, -0.85, 2.27), (dx + 0.06, -0.55, 2.42), H, white_p, 0.004)
text("Hall_Exit_Text", "EXIT", (dx + 0.062, -0.70, 2.345), 0.08, "+x", exit_m, 0.001)

# 実写スキャンの素材は実寸 UV を付ける
for o in H.objects:
    if o.type == 'MESH' and any(s.material and s.material.name in ("hall_carpet", "hall_wall_paint", "hall_door_oak") for s in o.material_slots):
        uv_box(o)
print("hallway ok", len(H.objects))

# 部屋の床は最初のブロックアウトで入口の外まで伸ばしていたので、入口の壁の廊下側(y=0.23)で切る
fl = D.objects["Floor"]
for v in fl.data.vertices:
    wco = fl.matrix_world @ v.co
    if wco.y < YN:
        wco.y = YN
        v.co = fl.matrix_world.inverted() @ wco
fl.data.update()
