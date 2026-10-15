"""段階5: ゆっくり前進するカメラ(10秒/24fps)と連番レンダー設定。Blender 内で exec する。"""
import bpy, os, math
from mathutils import Vector

D = bpy.data
SC = bpy.context.scene
ROOT = os.path.dirname(D.filepath)

FPS, SECONDS = 24, 10
DOLLY = 0.85   # 視線方向へ進む距離(m)
RISE = -0.03   # わずかに下げて机と床へ視線を寄せる

cam = D.objects["Cam_Main"]
cam.animation_data_clear()
start = Vector((0.0, 0.0, 1.10))
fwd = Vector((-math.sin(math.radians(21.5)), math.cos(math.radians(21.5)), 0.0))
end = start + fwd * DOLLY + Vector((0, 0, RISE))

SC.render.fps = FPS
SC.frame_start = 1
SC.frame_end = FPS * SECONDS
cam.location = start
cam.keyframe_insert("location", frame=SC.frame_start)
cam.location = end
cam.keyframe_insert("location", frame=SC.frame_end)
# 始まりと終わりをなめらかに
from bpy_extras import anim_utils
ad = cam.animation_data
bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)  # Blender 5 のスロット付きアクション
for fc in bag.fcurves:
    for k in fc.keyframe_points:
        k.interpolation = 'SINE'
        k.easing = 'EASE_IN_OUT'
SC.frame_set(1)

# 連番 PNG(途中から再開しやすい)
os.makedirs(os.path.join(ROOT, "frames"), exist_ok=True)
SC.render.filepath = os.path.join(ROOT, "frames", "frame_")
SC.render.image_settings.file_format = 'PNG'
SC.render.image_settings.color_mode = 'RGB'
SC.render.use_overwrite = False
SC.render.use_placeholder = True
SC.render.resolution_x, SC.render.resolution_y, SC.render.resolution_percentage = 1536, 1024, 100

cy = SC.cycles
cy.samples = 96
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.02
cy.use_denoising = True
SC.render.use_persistent_data = True
SC.camera = cam
print("animation ok", tuple(round(x, 3) for x in end))
