"""段階4: 深夜の照明。Blender 内で exec する。調整値は LIGHTS にまとめる。"""
import bpy, math

D = bpy.data
SC = bpy.context.scene

LIGHTS = {
    "desk_spot_w": 30.0, "desk_fill_w": 1.2, "monitor_w": 5.0, "monitor_emit": 1.3,
    "globe_w": 32.0, "globe_emit": 9.0, "window_w": 24.0, "backdrop_emit": 1.0,
    "world": 0.015, "exposure": 0.7, "bounce_w": 8.0,
    "moon_strength": 3.4, "moon_angle_deg": 1.2,
}
WARM = (1.0, 0.62, 0.32)

# 確認用ライトを外す
c = D.collections.get("99_BlockoutLight")
if c:
    for o in list(c.objects):
        D.objects.remove(o, do_unlink=True)
    D.collections.remove(c)

L = D.collections.get("13_Lighting") or D.collections.new("13_Lighting")
if L.name not in SC.collection.children:
    SC.collection.children.link(L)
for o in list(L.objects):
    D.objects.remove(o, do_unlink=True)


def light(name, kind, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), color=WARM, power=10.0, **kw):
    ld = D.lights.get(name) or D.lights.new(name, kind)
    ld.type = kind
    ld.color = color
    ld.energy = power
    for k, v in kw.items():
        setattr(ld, k, v)
    o = D.objects.new(name, ld)
    L.objects.link(o)
    if parent:
        o.parent = parent
    o.location = loc
    o.rotation_euler = rot
    return o


def set_emit(mat, strength):
    b = next(n for n in D.materials[mat].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Emission Strength"].default_value = strength


# デスクランプ: シェード内のスポット + シェード内側を照らす小さな点光源
shade = D.objects["DP_Lamp_Shade"]
light("Light_DeskLamp_Spot", 'SPOT', shade, (0, 0, -0.045), (0, 0, 0), WARM, LIGHTS["desk_spot_w"],
      spot_size=math.radians(92), spot_blend=0.6, shadow_soft_size=0.025)
light("Light_DeskLamp_Fill", 'POINT', shade, (0, 0, -0.03), (0, 0, 0), WARM, LIGHTS["desk_fill_w"], shadow_soft_size=0.02)
bulb = D.objects["DP_Lamp_Bulb"]
bulb.visible_shadow = False

# モニター: 画面と同じ大きさの面光源(+x 向き)
scr = D.objects["DP_Mon_Screen"]
light("Light_Monitor", 'AREA', scr, (0.004, 0, 0), (0, math.radians(-90), 0), (0.75, 0.82, 0.95), LIGHTS["monitor_w"],
      shape='RECTANGLE', size=0.39, size_y=0.70)
set_emit("monitor_screen", LIGHTS["monitor_emit"])

# 球形ランプ: 球自体は影を落とさない
globe = D.objects["Shelf_GlobeLamp"]
globe.visible_shadow = False
light("Light_Globe", 'POINT', None, tuple(globe.location), (0, 0, 0), (1.0, 0.66, 0.36), LIGHTS["globe_w"], shadow_soft_size=0.08)
set_emit("lamp_globe_glass", LIGHTS["globe_emit"])

# 窓: 外からの青い夜の光
win = light("Light_Window", 'AREA', None, (0.30, 5.30, 1.72), (math.radians(-90), 0, 0), (0.42, 0.52, 0.85), LIGHTS["window_w"],
            shape='RECTANGLE', size=2.45, size_y=1.50)
# 月明かり: 窓から斜め下へ。ベッドとラグに窓枠の影を落とす
from mathutils import Vector
moon_dir = Vector((-0.30, -1.0, -0.78)).normalized()
moon = light("Light_Moon", 'SUN', None, (0.3, 6.5, 3.5), tuple(moon_dir.to_track_quat('-Z', 'Y').to_euler()),
             (0.58, 0.70, 1.0), LIGHTS["moon_strength"], angle=math.radians(LIGHTS["moon_angle_deg"]))
D.objects["Win_Glass"].visible_shadow = False  # 屈折するガラスは影を遮るので月光を通す

# ランプの光が天井と壁で跳ね返った分の弱い暖色(画面外、カメラ側の天井付近)
light("Light_Bounce_Warm", 'AREA', None, (-0.9, 1.6, 2.62), (0, 0, 0), (1.0, 0.70, 0.45), LIGHTS["bounce_w"],
      shape='RECTANGLE', size=2.2, size_y=2.6)
for o in L.objects:
    o.visible_camera = False
    o.visible_transmission = False  # 窓ガラス越しに光源の面が見えないように

# 夜景の明るさ
for n in D.materials["night_campus"].node_tree.nodes:
    if n.type == "EMISSION":
        n.inputs["Strength"].default_value = LIGHTS["backdrop_emit"]

# ワールド: ごく暗い紺
w = SC.world
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.10, 0.14, 0.30, 1)
bg.inputs[1].default_value = LIGHTS["world"]

# 色管理
vs = SC.view_settings
try:
    vs.view_transform = 'AgX'
except TypeError as e:
    print("view transform:", e)
# look の列挙は表示変換ごとに変わるので try で設定する
for want in ("AgX - Medium High Contrast", "Medium High Contrast"):
    try:
        vs.look = want
        break
    except TypeError:
        pass
vs.exposure = LIGHTS["exposure"]

# レンダー設定
cy = SC.cycles
cy.use_denoising = True
cy.max_bounces = 8
cy.glossy_bounces = 4
cy.transmission_bounces = 8
cy.sample_clamp_indirect = 8.0
cy.use_light_tree = True
# 革の座面が白く光りすぎないように
lb = next(n for n in D.materials["leather_green"].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
lb.inputs["Roughness"].default_value = 0.62
lb.inputs["Coat Weight"].default_value = 0.0
lb.inputs["Specular IOR Level"].default_value = 0.25  # 斜めから見た壁の映り込みで白く見えるのを抑える
lb.inputs["Roughness"].default_value = 0.7
print("lighting ok", vs.view_transform, vs.look)
