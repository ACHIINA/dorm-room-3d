"""段階1: 部屋・窓・机・ベッド・椅子のブロックアウトとカメラ配置。
実行: blender -b --factory-startup --python scripts/01_blockout.py
"""
import bpy, os, math
from mathutils import Vector

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(OUT, "renders"), exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.name = "DormRoom"
sc.unit_settings.system = 'METRIC'


def coll(n):
    c = bpy.data.collections.new(n)
    sc.collection.children.link(c)
    return c


def mat(n, col):
    m = bpy.data.materials.new(n)
    m.use_nodes = True
    b = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = 0.8
    m.diffuse_color = (*col, 1)
    return m


def box(n, lo, hi, c, m):
    lo = Vector(lo)
    hi = Vector(hi)
    me = bpy.data.meshes.new(n)
    v = [(x, y, z) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.update()
    o = bpy.data.objects.new(n, me)
    c.objects.link(o)
    me.materials.append(m)
    # 原点を箱の中心へ
    ctr = (lo + hi) / 2
    me.transform(__import__("mathutils").Matrix.Translation(-ctr))
    o.location = ctr
    return o


M_wall = mat("BO_wall", (0.75, 0.70, 0.62))
M_floor = mat("BO_floor", (0.35, 0.22, 0.13))
M_wood = mat("BO_wood", (0.40, 0.24, 0.13))
M_bed = mat("BO_bedding", (0.30, 0.33, 0.22))
M_frame = mat("BO_windowframe", (0.08, 0.08, 0.08))
M_mat = mat("BO_mattress", (0.80, 0.78, 0.72))

# 部屋: x -2.77..1.60 / y 0.35..5.00 / 天井 2.70（単位 m、カメラは原点付近の入口）
X0, X1, Y0, Y1, H = -2.77, 1.60, 0.35, 5.00, 2.70
T = 0.12
R = coll("01_Room")
box("Floor", (X0 - T, Y0 - 1.5, -0.1), (X1 + T, Y1 + T, 0), R, M_floor)
box("Ceiling", (X0 - T, Y0 - T, H), (X1 + T, Y1 + T, H + 0.1), R, M_wall)
box("Wall_Left", (X0 - T, Y0 - T, 0), (X0, Y1 + T, H), R, M_wall)
box("Wall_Right", (X1, Y0 - T, 0), (X1 + T, Y1 + T, H), R, M_wall)
# 入口壁（ドア開口 x -0.45..0.45, 高さ 2.05）
box("Wall_Front_L", (X0, Y0 - T, 0), (-0.45, Y0, H), R, M_wall)
box("Wall_Front_R", (0.45, Y0 - T, 0), (X1, Y0, H), R, M_wall)
box("Wall_Front_Top", (-0.45, Y0 - T, 2.05), (0.45, Y0, H), R, M_wall)
# ドア板: 左の枠を軸に室内側へ約145°開き、画面左端に細く見える
door = box("Door_Leaf", (0, -0.02, 0), (0.85, 0.02, 2.03), R, M_wall)
door.data.transform(__import__("mathutils").Matrix.Translation((0.425, 0, 1.015)))
door.location = (-0.45, Y0, 0)
door.rotation_euler.z = math.radians(145)
# 奥壁（窓開口）
WX0, WX1, WZ0, WZ1 = -0.95, 1.50, 0.93, 2.48
box("Wall_Back_L", (X0, Y1, 0), (WX0, Y1 + T, H), R, M_wall)
box("Wall_Back_R", (WX1, Y1, 0), (X1, Y1 + T, H), R, M_wall)
box("Wall_Back_Below", (WX0, Y1, 0), (WX1, Y1 + T, WZ0), R, M_wall)
box("Wall_Back_Above", (WX0, Y1, WZ1), (WX1, Y1 + T, H), R, M_wall)

W = coll("02_Window")
f = 0.05
box("Win_Sill", (WX0 - 0.03, Y1 - 0.10, WZ0 - 0.04), (WX1 + 0.03, Y1 + T, WZ0), W, M_wall)
box("Win_Frame_Bottom", (WX0, Y1 + 0.03, WZ0), (WX1, Y1 + 0.09, WZ0 + f), W, M_frame)
box("Win_Frame_Top", (WX0, Y1 + 0.03, WZ1 - f), (WX1, Y1 + 0.09, WZ1), W, M_frame)
for i, x in enumerate([WX0, WX0 + (WX1 - WX0) / 3, WX0 + 2 * (WX1 - WX0) / 3, WX1 - f]):
    box(f"Win_Mullion_{i}", (x, Y1 + 0.03, WZ0), (x + f, Y1 + 0.09, WZ1), W, M_frame)

# 机: 左壁沿いに奥へ伸びる。手前側に引き出し袖
D = coll("03_Desk")
dx0, dx1, dy0, dy1 = X0 + 0.02, X0 + 0.72, 1.90, 3.80
box("Desk_Top", (dx0, dy0, 0.72), (dx1, dy1, 0.76), D, M_wood)
box("Desk_Pedestal", (dx0 + 0.03, dy0 + 0.03, 0.14), (dx1 - 0.03, dy0 + 0.62, 0.72), D, M_wood)
box("Desk_Apron", (dx0 + 0.03, dy0 + 0.62, 0.60), (dx1 - 0.03, dy1 - 0.03, 0.72), D, M_wood)
legs = [(dx0 + 0.05, dy0 + 0.05), (dx1 - 0.09, dy0 + 0.05), (dx0 + 0.05, dy0 + 0.56),
        (dx1 - 0.09, dy0 + 0.56), (dx0 + 0.05, dy1 - 0.09), (dx1 - 0.09, dy1 - 0.09)]
for i, (x, y) in enumerate(legs):
    box(f"Desk_Leg_{i}", (x, y, 0), (x + 0.04, y + 0.04, 0.60 if i > 3 else 0.14), D, M_wood)

# 椅子: 机(-x)に向く
C = coll("04_Chair")
cx, cy = -1.50, 2.50
parts = [box("Chair_Seat", (cx - 0.23, cy - 0.23, 0.42), (cx + 0.23, cy + 0.23, 0.47), C, M_bed),
         box("Chair_Back", (cx + 0.21, cy - 0.22, 0.62), (cx + 0.25, cy + 0.22, 0.86), C, M_wood)]
for i, (sx, sy) in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1)]):
    x = cx + sx * 0.20
    y = cy + sy * 0.20
    parts.append(box(f"Chair_Leg_{i}", (x - 0.02, y - 0.02, 0), (x + 0.02, y + 0.02, 0.86 if sx > 0 else 0.42), C, M_wood))
root = bpy.data.objects.new("Chair_Root", None)
C.objects.link(root)
root.location = (cx, cy, 0)
for p in parts:
    p.parent = root
    p.location = p.location - root.location
root.rotation_euler.z = math.radians(-12)

# ベッド: 頭が右壁、長辺が画面と平行
B = coll("05_Bed")
bx0, bx1, by0, by1 = -0.62, 1.55, 2.70, 4.30
box("Bed_Frame", (bx0, by0, 0.20), (bx1, by1, 0.34), B, M_wood)
box("Bed_Mattress", (bx0 + 0.03, by0 + 0.03, 0.34), (bx1 - 0.06, by1 - 0.03, 0.58), B, M_mat)
box("Bed_Duvet", (bx0 - 0.02, by0 - 0.03, 0.30), (bx1 - 0.55, by1 + 0.02, 0.66), B, M_bed)
box("Bed_Headboard", (bx1 - 0.05, by0, 0.20), (bx1, by1, 0.95), B, M_wood)
for i, (x, y) in enumerate([(bx0 + 0.04, by0 + 0.04), (bx0 + 0.04, by1 - 0.09),
                            (bx1 - 0.09, by0 + 0.04), (bx1 - 0.09, by1 - 0.09)]):
    box(f"Bed_Leg_{i}", (x, y, 0), (x + 0.05, y + 0.05, 0.20), B, M_wood)

# カメラ: 入口、目線 1.10m、左へ 21.5°、シフトで垂直線を保つ
cd = bpy.data.cameras.new("Cam_Main")
cam = bpy.data.objects.new("Cam_Main", cd)
sc.collection.objects.link(cam)
cam.location = (0, 0, 1.10)
cam.rotation_euler = (math.radians(90), 0, math.radians(21.5))
cd.lens = 28
cd.sensor_width = 36
cd.shift_y = -0.118
cd.clip_start = 0.05
sc.camera = cam
sc.render.resolution_x = 1536
sc.render.resolution_y = 1024

# 確認用の仮ライト（段階4で置き換える）
L = coll("99_BlockoutLight")
ld = bpy.data.lights.new("BO_Area", 'AREA')
ld.energy = 90
ld.size = 3
lo = bpy.data.objects.new("BO_Area", ld)
L.objects.link(lo)
lo.location = (-0.5, 2.6, 2.6)
w = bpy.data.worlds.new("World")
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.02, 0.03, 0.06, 1)

sc.render.engine = 'CYCLES'
sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.render.filepath = os.path.join(OUT, "renders", "01_blockout.png")
sc.render.image_settings.file_format = 'PNG'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "dorm_room.blend"))
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_mainfile()
