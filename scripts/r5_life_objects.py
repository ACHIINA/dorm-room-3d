"""リアル版 段階R5: 暮らしの機能で使う新しいオブジェクト。Blender 内で exec する。
名前の先頭は Godot 側の操作判定(room_setup.gd / life.gd)と対応させている。"""
import bpy, os, math
from mathutils import Vector

ROOT = os.path.dirname(bpy.data.filepath)
exec(open(os.path.join(ROOT, "scripts", "helpers.py")).read())

C = coll("22_Life")
rm("Calendar_", "Wall_Switch_", "Ceiling_Lamp_", "Kettle_", "DP_Mug_Coffee", "Fishbowl_", "Fish_", "WateringCan_")

steel = mat("metal_steel_brushed", (0.62, 0.62, 0.63), 0.28, 1.0)
blackp = mat("plastic_black")
brass = mat("metal_brass")
plastic_w = mat("plastic_white_outlet", (0.78, 0.76, 0.72), 0.35)
paper = mat("calendar_page", (0.90, 0.88, 0.84), 0.85)
opal = mat("pendant_opal_glass", (0.88, 0.86, 0.82), 0.25, 0, ((1.0, 0.78, 0.55), 0.0))
bulb = mat("pendant_bulb", (1.0, 0.85, 0.6), 0.3, 0, ((1.0, 0.75, 0.45), 0.0))
coffee = mat("coffee_liquid", (0.045, 0.022, 0.010), 0.06)
bowl_glass = mat("fishbowl_bowl_glass", (0.85, 0.92, 0.92), 0.03)
water = mat("fishbowl_water", (0.55, 0.72, 0.70), 0.05)
gravel = mat("fishbowl_gravel", (0.42, 0.36, 0.30), 0.9)
goldfish = mat("goldfish_orange", (0.85, 0.30, 0.05), 0.35)
can_green = mat("wateringcan_green", (0.16, 0.26, 0.20), 0.45, 0.6)

# ---- 壁掛けカレンダー(右の壁、ベッドの足元側) ----
X1 = 1.60
box("Calendar_Page", (X1 - 0.006, 1.75, 1.33), (X1 - 0.001, 2.05, 1.75), C, paper, 0.001)
box("Calendar_Backing", (X1 - 0.003, 1.745, 1.325), (X1, 2.055, 1.755), C, mat("frame_black"))
box("Calendar_Clip", (X1 - 0.014, 1.86, 1.73), (X1 - 0.004, 1.94, 1.775), C, blackp, 0.002)

# ---- 照明のスイッチ(ドアの右、入口の壁) ----
Y0 = 0.35
box("Wall_Switch_Plate", (0.58, Y0, 1.16), (0.66, Y0 + 0.007, 1.28), C, plastic_w, 0.002)
box("Wall_Switch_Rocker", (0.605, Y0 + 0.007, 1.195), (0.635, Y0 + 0.016, 1.245), C, plastic_w, 0.002)

# ---- 天井のペンダントライト ----
lx, ly = -0.55, 2.75
cyl("Ceiling_Lamp_Canopy", (lx, ly, 2.675), (lx, ly, 2.70), 0.06, 0.06, C, brass, 24)
tube("Ceiling_Lamp_Cord", [(lx, ly, 2.68), (lx, ly, 2.45), (lx, ly, 2.27)], 0.003, C, blackp, 2)
lathe("Ceiling_Lamp_Cap", [(0.012, 0.0), (0.035, -0.01), (0.04, -0.04), (0.03, -0.045)], (lx, ly, 2.27), C, brass)
lathe("Ceiling_Lamp_Shade", [(0.03, 0.0), (0.09, -0.02), (0.15, -0.07), (0.19, -0.14), (0.20, -0.17),
                              (0.195, -0.172), (0.185, -0.14), (0.145, -0.07), (0.085, -0.022), (0.028, -0.004)],
      (lx, ly, 2.23), C, opal, cap=False)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=0.035)
_finish("Ceiling_Lamp_Bulb", bm, C, bulb, smooth=True, loc=(lx, ly, 2.17))

# ---- 電気ケトル(手前の棚の上) ----
kx, ky, kz = 0.62, 1.62, 0.58
cyl("Kettle_Base", (kx, ky, kz), (kx, ky, kz + 0.022), 0.085, 0.082, C, blackp, 32)
lathe("Kettle_Body", [(0.0005, 0.0), (0.075, 0.0), (0.080, 0.03), (0.078, 0.12), (0.066, 0.18), (0.045, 0.205),
                      (0.044, 0.212), (0.0005, 0.212)], (kx, ky, kz + 0.022), C, steel, seg=36)
cyl("Kettle_Knob", (kx, ky, kz + 0.233), (kx, ky, kz + 0.25), 0.014, 0.012, C, blackp)
tube("Kettle_Handle", [(kx + 0.06, ky, kz + 0.07), (kx + 0.115, ky, kz + 0.09), (kx + 0.12, ky, kz + 0.17),
                       (kx + 0.09, ky, kz + 0.205), (kx + 0.045, ky, kz + 0.205)], 0.011, C, blackp, 3)
cyl("Kettle_Spout", (kx - 0.07, ky, kz + 0.13), (kx - 0.115, ky, kz + 0.19), 0.016, 0.009, C, steel)

# ---- マグの中のコーヒー(Godot で量を変える) ----
cyl("DP_Mug_Coffee", (-2.20, 2.24, 0.76 + 0.083), (-2.20, 2.24, 0.76 + 0.085), 0.0385, 0.0385, C, coffee, 32)

# ---- 金魚鉢(窓台) ----
fx, fy, fz = 0.12, 5.07, 0.93
lathe("Fishbowl_Bowl", [(0.045, 0.0), (0.085, 0.02), (0.108, 0.08), (0.100, 0.15), (0.075, 0.195), (0.078, 0.205),
                        (0.074, 0.207), (0.071, 0.196), (0.096, 0.15), (0.104, 0.08), (0.082, 0.024), (0.0005, 0.004)],
      (fx, fy, fz), C, bowl_glass, seg=40, cap=False)
lathe("Fishbowl_Water", [(0.0005, 0.006), (0.08, 0.024), (0.101, 0.08), (0.094, 0.15), (0.0005, 0.15)], (fx, fy, fz), C, water, seg=40)
cyl("Fishbowl_Gravel", (fx, fy, fz + 0.006), (fx, fy, fz + 0.024), 0.07, 0.085, C, gravel, 32)
# 金魚(体と尾びれを 1 つのメッシュに)
bm = bmesh.new()
b = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)["verts"]
bmesh.ops.scale(bm, vec=(0.022, 0.009, 0.012), verts=b)
t = [bm.verts.new(v) for v in ((-0.018, 0, 0.0), (-0.04, 0, 0.014), (-0.036, 0, 0.0), (-0.04, 0, -0.012))]
bm.faces.new((t[0], t[1], t[2]))
bm.faces.new((t[0], t[2], t[3]))
fish = _finish("Fish_Goldfish", bm, C, goldfish, smooth=True, loc=(fx + 0.04, fy, fz + 0.08))
solidify(fish, 0.001)

# ---- じょうろ(棚の横の床) ----
wx, wy = -0.70, 4.72
lathe("WateringCan_Body", [(0.0005, 0.0), (0.07, 0.0), (0.072, 0.01), (0.07, 0.15), (0.06, 0.16), (0.0005, 0.16)], (wx, wy, 0.0), C, can_green, seg=32)
cyl("WateringCan_Spout", (wx + 0.05, wy, 0.04), (wx + 0.20, wy, 0.17), 0.012, 0.007, C, can_green)
cyl("WateringCan_Rose", (wx + 0.20, wy, 0.17), (wx + 0.215, wy, 0.18), 0.018, 0.02, C, can_green)
tube("WateringCan_Handle", [(wx - 0.06, wy, 0.06), (wx - 0.10, wy, 0.12), (wx - 0.06, wy, 0.21), (wx + 0.02, wy, 0.20), (wx + 0.03, wy, 0.16)], 0.008, C, can_green, 3)
print("life objects ok", len(C.objects))

# 金魚鉢と水は透過させる(Godot 側は書き出しで半透明に変換)
for m, (ior, rough) in ((bowl_glass, (1.5, 0.02)), (water, (1.33, 0.03))):
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = ior
    b.inputs["Roughness"].default_value = rough
