"""リアル版 段階R3: 配線・電源タップ・コンセント・椅子に掛けたスウェット・ほこりと汚れ・被写界深度。
Blender 内で exec する(helpers.py と r1_pbr.py の build を使う)。"""
import bpy, os, math
from mathutils import Vector, noise

ROOT = os.path.dirname(bpy.data.filepath)
exec(open(os.path.join(ROOT, "scripts", "helpers.py")).read())
_ns = {}
exec(open(os.path.join(ROOT, "scripts", "r1_pbr.py")).read().split("# ---------------- 実行 ----------------")[0], _ns)
build, uv_grid = _ns["build"], _ns["uv_grid"]

C = coll("21_Details")
rm("RD_")
rubber = mat("rubber_cable_black", (0.012, 0.012, 0.012), 0.55)
plastic_w = mat("plastic_white_outlet", (0.78, 0.76, 0.72), 0.35)
X0 = -2.77

# ---- 電源タップ(机の下の床) ----
sx, sy = -2.55, 3.15
box("RD_PowerStrip", (-0.03, -0.17, 0), (0.03, 0.17, 0.035), C, plastic_w, 0.006, 3, at=(sx, sy, 0.0), rot=(0, 0, math.radians(8)))
for i in range(4):
    y = -0.12 + i * 0.065
    box(f"RD_PowerStrip_Socket_{i}", (-0.012, -0.014, 0), (0.012, 0.014, 0.002), C, mat("plastic_dark", (0.05, 0.05, 0.05), 0.5), at=(sx + y * math.sin(math.radians(-8)), sy + y * math.cos(math.radians(8)), 0.035))
box("RD_Switch", (-0.012, -0.01, 0), (0.012, 0.01, 0.008), C, mat("plastic_red_switch", (0.5, 0.05, 0.03), 0.3), at=(sx, sy - 0.15, 0.035))

# ---- 壁のコンセント ----
for n, (y, z) in {"RD_Outlet_Desk": (2.95, 0.30), "RD_Outlet_Shelf": (None, 0.30)}.items():
    if y is None:
        box(n, (-0.035, -0.006, -0.058), (0.035, 0, 0.058), C, plastic_w, 0.002, at=(-0.70, 5.0, z))
    else:
        box(n, (0, -0.035, -0.058), (0.006, 0.035, 0.058), C, plastic_w, 0.002, at=(X0, y, z))

# ---- 配線: 机の上の機器 → 机の奥の隙間 → 床の電源タップ(机の前から見えるたるみ) ----
cables = {
    "RD_Cable_Monitor": [(-2.62, 2.64, 0.93), (-2.69, 2.68, 0.80), (-2.758, 2.74, 0.766), (-2.762, 2.80, 0.62),
                         (-2.70, 2.95, 0.30), (-2.62, 3.05, 0.06), (-2.57, 3.08, 0.02), (sx - 0.01, sy - 0.09, 0.03)],
    "RD_Cable_Lamp": [(-2.62, 3.62, 0.768), (-2.68, 3.52, 0.767), (-2.75, 3.38, 0.766), (-2.762, 3.30, 0.60),
                      (-2.71, 3.25, 0.25), (-2.60, 3.23, 0.04), (sx, sy + 0.06, 0.03)],
    "RD_Cable_Speaker": [(-2.66, 3.32, 0.80), (-2.73, 3.25, 0.77), (-2.762, 3.10, 0.70), (-2.74, 3.0, 0.35),
                         (-2.62, 3.12, 0.03), (sx + 0.01, sy - 0.02, 0.03)],
    "RD_Cable_Charger": [(-2.20, 3.05, 0.765), (-2.10, 3.02, 0.70), (-2.08, 3.00, 0.45), (-2.20, 3.06, 0.10),
                         (-2.40, 3.12, 0.012), (sx + 0.02, sy + 0.12, 0.03)],
}
for n, pts in cables.items():
    o = tube(n, pts, 0.0032 if "Speaker" not in n else 0.0018, C, rubber, 3)
    o.data.resolution_u = 16
# 机の上の充電ケーブルの先(スマホ用の端子)
box("RD_ChargerPlug", (-0.008, -0.004, -0.003), (0.008, 0.004, 0.003), C, plastic_w, 0.001, at=(-2.20, 3.05, 0.768))

# ---- 椅子に掛けたスウェット(クロス) ----
chair = D.objects["Chair_Root"]
rm("RD_Sweatshirt")
bpy.context.view_layer.update()
Mw = chair.matrix_world.copy()
# 背もたれは薄い曲面 1 枚で布が突き抜けるので、厚みのある箱で近似した衝突用の形を使う
cols = []
for n, lo, hi, rot in [("RD_ColBack", (-0.03, -0.235, -0.13), (0.03, 0.235, 0.13), (0, math.radians(13), 0)),
                       ("RD_ColSeat", (-0.23, -0.23, -0.03), (0.22, 0.23, 0.03), (0, 0, 0))]:
    pc = box(n, lo, hi, C, None, 0.02, 3)
    pc.parent = chair
    pc.location = (0.255, 0, 0.70) if n == "RD_ColBack" else (0, 0, 0.43)
    pc.rotation_euler = rot
    cols.append(pc)
for x, y in ((0.23, 0.17), (0.23, -0.17)):
    pc = box("RD_ColUpright", (-0.025, -0.025, -0.25), (0.025, 0.025, 0.25), C, None)
    pc.parent = chair
    pc.location = (x, y, 0.62)
    pc.rotation_euler = (0, math.radians(13), 0)
    cols.append(pc)
for o in cols:
    o.modifiers.new("Col", 'COLLISION')
    o.collision.thickness_outer = 0.008
    o.collision.cloth_friction = 60
floor = box("RD_FloorCol", (-3, 1.5, -0.02), (0, 4, 0), C, None)
floor.modifiers.new("Col", 'COLLISION')
bpy.context.view_layer.update()
NX, NY, W, H = 22, 48, 0.46, 1.05


def sfn(u, v):
    # 椅子のローカル: 背もたれ(x≈0.26)をまたいで前後に垂れる
    p = Mw @ Vector((0.27 - 0.45 + v * H, (u - 0.5) * W, 0.90 / 1.07 + 0.03 * noise.noise((u * 4, v * 4, 3.3))))
    return tuple(p)


sw = grid_mesh("RD_Sweatshirt", NX, NY, sfn, C, mat("fabric_sweat_gray", (0.2, 0.2, 0.2), 0.9))
md = sw.modifiers.new("Cloth", 'CLOTH')
s = md.settings
s.quality = 8
s.mass = 0.35
s.bending_stiffness = 0.25
s.shrink_min = -0.12
s.air_damping = 2.5
md.collision_settings.distance_min = 0.008
md.collision_settings.use_self_collision = True
md.collision_settings.self_distance_min = 0.004
md.point_cache.frame_end = 70
for f in range(1, 71):
    SC.frame_set(f)
me = D.meshes.new_from_object(sw.evaluated_get(bpy.context.evaluated_depsgraph_get()))
sw.modifiers.remove(md)
old = sw.data
sw.data = me
D.meshes.remove(old)
SC.frame_set(1)
for p in sw.data.polygons:
    p.use_smooth = True
for o in cols + [floor]:
    D.objects.remove(o, do_unlink=True)
uv_grid(sw, NX, NY, W, H)
solidify(sw, 0.007, 1)
subsurf(sw, 1)
build("fabric_sweat_gray", "cotton_jersey", (0.16, 0.165, 0.17), 1.0, 1.0, dict(sheen=0.5, bump=0.0012))
sw.parent = chair
sw.matrix_parent_inverse = chair.matrix_world.inverted()

# ---- ほこり: 上を向いた木の面にうっすら ----
def add_dust(mname, amount=0.22):
    m = D.materials[mname]
    nt = m.node_tree
    if any(n.name.startswith("dust_") for n in nt.nodes):
        return
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    base = b.inputs["Base Color"].links[0].from_socket
    rough = b.inputs["Roughness"].links[0].from_socket

    def N(t, name):
        n = nt.nodes.new(t)
        n.name = "dust_" + name
        return n

    geo = N("ShaderNodeNewGeometry", "geo")
    sep = N("ShaderNodeSeparateXYZ", "sep")
    nt.links.new(geo.outputs["Normal"], sep.inputs[0])
    up = N("ShaderNodeMapRange", "up")
    up.inputs["From Min"].default_value = 0.85
    up.inputs["From Max"].default_value = 1.0
    nt.links.new(sep.outputs["Z"], up.inputs["Value"])
    tc = N("ShaderNodeTexCoord", "tc")
    nz = N("ShaderNodeTexNoise", "noise")
    nz.inputs["Scale"].default_value = 18.0
    nz.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rmp = N("ShaderNodeMapRange", "patch")
    rmp.inputs["From Min"].default_value = 0.45
    rmp.inputs["From Max"].default_value = 0.75
    rmp.inputs["To Max"].default_value = amount
    nt.links.new(nz.outputs["Fac"], rmp.inputs["Value"])
    fac = N("ShaderNodeMath", "fac")
    fac.operation = 'MULTIPLY'
    nt.links.new(up.outputs["Result"], fac.inputs[0])
    nt.links.new(rmp.outputs["Result"], fac.inputs[1])
    mc = N("ShaderNodeMix", "color")
    mc.data_type = 'RGBA'
    sock = lambda nd, i, out=False: next(x for x in (nd.outputs if out else nd.inputs) if x.identifier == i)
    nt.links.new(fac.outputs[0], sock(mc, "Factor_Float"))
    nt.links.new(base, sock(mc, "A_Color"))
    sock(mc, "B_Color").default_value = (0.32, 0.30, 0.27, 1)
    nt.links.new(sock(mc, "Result_Color", True), b.inputs["Base Color"])
    mr = N("ShaderNodeMath", "rough")
    mr.operation = 'ADD'
    mr.use_clamp = True
    nt.links.new(rough, mr.inputs[0])
    m2 = N("ShaderNodeMath", "rough_k")
    m2.operation = 'MULTIPLY'
    m2.inputs[1].default_value = 2.0
    nt.links.new(fac.outputs[0], m2.inputs[0])
    nt.links.new(m2.outputs[0], mr.inputs[1])
    nt.links.new(mr.outputs[0], b.inputs["Roughness"])
    cw = b.inputs["Coat Weight"]
    if not cw.is_linked:
        inv = N("ShaderNodeMath", "coat")
        inv.operation = 'MULTIPLY_ADD'
        inv.inputs[1].default_value = -cw.default_value * 3
        inv.inputs[2].default_value = cw.default_value
        inv.use_clamp = True
        nt.links.new(fac.outputs[0], inv.inputs[0])
        nt.links.new(inv.outputs[0], cw)


for mname in ("wood_walnut", "wood_walnut_dark"):
    add_dust(mname)

# ---- 壁: 隅と床際のわずかなくすみ(AO) ----
wm = D.materials["wall_plaster"]
nt = wm.node_tree
if not any(n.name == "grime_ao" for n in nt.nodes):
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    base = b.inputs["Base Color"].links[0].from_socket
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.name = "grime_ao"
    ao.inputs["Distance"].default_value = 0.35
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.name = "grime_range"
    mr.inputs["To Min"].default_value = 0.78
    nt.links.new(ao.outputs["AO"], mr.inputs["Value"])
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.name = "grime_mul"
    vm.operation = 'SCALE'
    nt.links.new(base, vm.inputs[0])
    nt.links.new(mr.outputs["Result"], vm.inputs["Scale"])
    nt.links.new(vm.outputs["Vector"], b.inputs["Base Color"])

# ---- カメラ: 椅子にピント、窓の外がほんのりボケる ----
cam = D.objects["Cam_Main"].data
cam.dof.use_dof = True
cam.dof.focus_object = D.objects["Chair_Root"]
cam.dof.aperture_fstop = 2.8
print("details ok")
