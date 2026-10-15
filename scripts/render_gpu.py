"""バックグラウンド実行用: このプロセスの中だけ Metal GPU を有効にする(環境設定は保存しない)。
例: blender -b dorm_room.blend --python scripts/render_gpu.py -a
"""
import bpy

prefs = bpy.context.preferences
prefs.use_preferences_save = False
cp = prefs.addons["cycles"].preferences
cp.compute_device_type = 'METAL'
cp.refresh_devices()
for d in cp.devices:
    d.use = d.type != 'CPU'
bpy.context.scene.cycles.device = 'GPU'
print("devices:", [(d.name, d.type, d.use) for d in cp.devices])
