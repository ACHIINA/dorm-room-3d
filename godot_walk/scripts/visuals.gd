extends Node
## 見た目の仕上げ(AAA 寄り)。起動時に一度だけ実行する。
## 1. 光: SDFGI をやめ、部屋ごとの VoxelGI を起動時に焼き付ける(ランプのオンオフにもリアルタイムで追従)
## 2. 影: 光源に大きさを持たせて影のフチをやわらかく、接地部分の陰影(SSAO)を強める
## 3. カメラ: 自動露出、色調整、フィルムの粒子・周辺減光・わずかな色収差
## 4. 使用感: 単色の素材に、指紋や擦れのような粗さのムラと薄い汚れを重ねる。デカールで輪じみ・擦れ・水あと

@onready var main: Node = get_parent()
var env: Environment
var _cover: ColorRect

# VoxelGI の範囲(Godot 座標: 中心, 大きさ, 細かさ)
const GI_AREAS := [
	["Room313", Vector3(-0.585, 1.40, -2.77), Vector3(4.7, 2.9, 5.2), VoxelGI.SUBDIV_256],
	["Hallway", Vector3(0.0, 1.35, 0.69), Vector3(14.4, 2.8, 2.2), VoxelGI.SUBDIV_128],
	["Room315", Vector3(3.52, 1.40, -2.47), Vector3(3.7, 2.9, 4.6), VoxelGI.SUBDIV_128],
	["Lounge", Vector3(4.10, 1.40, 3.96), Vector3(5.9, 2.9, 4.8), VoxelGI.SUBDIV_128],
	["Shower", Vector3(-5.49, 1.30, 3.56), Vector3(3.1, 2.7, 4.0), VoxelGI.SUBDIV_128],
]


func _ready() -> void:
	env = main.get_node("WorldEnvironment").environment
	_show_cover()
	_setup_environment()
	_soften_lights()
	_add_wear()
	_add_decals()
	_add_post()
	# 焼き付けは描画が始まってから(数秒)
	await get_tree().process_frame
	await get_tree().process_frame
	_bake_gi()
	var tw := create_tween()
	tw.tween_property(_cover, "modulate:a", 0.0, 0.8)
	tw.tween_callback(_cover.queue_free)


# ---------------- 1. 光 ----------------
func _bake_gi() -> void:
	env.sdfgi_enabled = false
	var room: Node = main.get_node("Room")
	for a in GI_AREAS:
		var gi := VoxelGI.new()
		gi.name = "GI_" + a[0]
		gi.size = a[2]
		gi.subdiv = a[3]
		main.add_child(gi)
		gi.global_position = a[1]
		gi.bake(room)
		if gi.data:
			gi.data.energy = 0.85
			gi.data.propagation = 0.75
			gi.data.use_two_bounces = true
			gi.data.interior = true   # 空の光は窓のライトが担う(壁の外から漏れないように)
			gi.data.bias = 1.6
			gi.data.normal_bias = 0.6


func _setup_environment() -> void:
	# 霞が GI の光を拾うと部屋全体が乳白色になるので、霞は直接の光(ランプ・月・太陽)だけで照らす
	env.volumetric_fog_gi_inject = 0.0
	env.ssao_enabled = true
	env.ssao_radius = 0.9
	env.ssao_intensity = 2.2
	env.ssao_power = 1.7
	env.ssao_detail = 0.6
	env.ssao_light_affect = 0.18     # 明るい所でも隅や接地部分に陰を残す
	env.ssil_enabled = true
	env.ssil_radius = 2.5
	env.ssil_intensity = 0.7
	env.glow_enabled = true
	env.glow_intensity = 0.55
	env.glow_bloom = 0.05
	env.glow_hdr_threshold = 1.1
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.06
	env.adjustment_saturation = 0.95
	# 自動露出: 暗い部屋から明るい廊下へ出ると、少し遅れて目が慣れる
	var ca := CameraAttributesPractical.new()
	ca.auto_exposure_enabled = true
	# 補正の幅は小さく(夜の部屋は暗いまま、廊下の蛍光灯ではわずかに絞る)
	ca.auto_exposure_scale = 0.22
	ca.auto_exposure_speed = 0.7
	ca.auto_exposure_min_sensitivity = 70.0
	ca.auto_exposure_max_sensitivity = 130.0
	main.get_node("WorldEnvironment").camera_attributes = ca


# ---------------- 2. 影 ----------------
func _soften_lights() -> void:
	for l in main.find_children("*", "Light3D", true, false):
		if l is DirectionalLight3D:
			l.light_angular_distance = 0.8
		elif l is SpotLight3D or l is OmniLight3D:
			if l.light_size == 0.0:
				l.light_size = 0.06
		l.shadow_blur = 1.3


# ---------------- 3. カメラの仕上げ(画面全体のシェーダー) ----------------
const POST_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform float grain = 0.032;
uniform float vignette = 0.28;
uniform float aberration = 0.0012;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 d = uv - 0.5;
	float r2 = dot(d, d);
	// 画面の端ほどわずかに色がずれる
	vec2 off = d * aberration * r2 * 4.0;
	vec3 c = vec3(texture(screen_tex, uv + off).r, texture(screen_tex, uv).g, texture(screen_tex, uv - off).b);
	// 周辺減光
	c *= 1.0 - vignette * smoothstep(0.08, 0.55, r2);
	// フィルムの粒子(暗部ほど目立つ)
	float n = hash(uv * vec2(1920.0, 1080.0) + fract(TIME) * 61.0) - 0.5;
	c += n * grain * (1.0 - 0.6 * dot(c, vec3(0.333)));
	COLOR = vec4(c, 1.0);
}
"""


func _add_post() -> void:
	var layer := CanvasLayer.new()
	layer.layer = -1   # 操作説明などの表示より下(3D の画面だけにかける)
	add_child(layer)
	var r := ColorRect.new()
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := Shader.new()
	sh.code = POST_SHADER
	var m := ShaderMaterial.new()
	m.shader = sh
	r.material = m
	layer.add_child(r)


func _show_cover() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 30
	add_child(layer)
	_cover = ColorRect.new()
	_cover.color = Color(0.03, 0.03, 0.035)
	_cover.set_anchors_preset(Control.PRESET_FULL_RECT)
	layer.add_child(_cover)
	var l := Label.new()
	l.text = "部屋の光を計算しています…"
	l.set_anchors_preset(Control.PRESET_FULL_RECT)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.add_theme_font_size_override("font_size", 20)
	l.add_theme_color_override("font_color", Color(0.9, 0.86, 0.8, 0.8))
	_cover.add_child(l)


# ---------------- 4. 使用感 ----------------
func _noise_tex(freq: float, lo: float, hi: float, seed: int, cellular := false) -> NoiseTexture2D:
	var n := FastNoiseLite.new()
	n.seed = seed
	n.frequency = freq
	n.noise_type = FastNoiseLite.TYPE_CELLULAR if cellular else FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	n.fractal_octaves = 5
	var t := NoiseTexture2D.new()
	t.width = 512
	t.height = 512
	t.seamless = true
	t.noise = n
	var g := Gradient.new()
	g.set_color(0, Color(lo, lo, lo))
	g.set_color(1, Color(hi, hi, hi))
	t.color_ramp = g
	return t


func _add_wear() -> void:
	# 単色の素材(画像を持たないもの)に、粗さのムラと薄い汚れを立体投影で重ねる
	var rough := _noise_tex(0.012, 0.72, 1.0, 7)
	var dirt := _noise_tex(0.006, 0.86, 1.0, 21)
	var done := {}
	for mi in main.get_node("Room").find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = mi.mesh
		if mesh == null:
			continue
		for s in mesh.get_surface_count():
			var m := mesh.surface_get_material(s)
			if not (m is StandardMaterial3D) or done.has(m):
				continue
			done[m] = true
			var sm: StandardMaterial3D = m
			if sm.albedo_texture or sm.emission_enabled or sm.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
				continue
			# 金属やつやのある面(ステンレス・画面・鏡)はムラがまだらに見えるので重ねない
			if sm.metallic > 0.5 or sm.roughness < 0.3:
				continue
			sm.roughness_texture = rough
			sm.uv1_triplanar = true
			sm.uv1_world_triplanar = true
			sm.uv1_scale = Vector3(1.6, 1.6, 1.6)
			sm.detail_enabled = true
			sm.detail_blend_mode = BaseMaterial3D.BLEND_MODE_MUL
			sm.detail_albedo = dirt


func _ring_tex() -> ImageTexture:
	# コーヒーの輪じみ(縁が濃い、少し欠けた輪)
	var s := 256
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	for y in s:
		for x in s:
			var d := Vector2(x - s / 2.0, y - s / 2.0)
			var r := d.length() / (s * 0.42)
			var a := atan2(d.y, d.x)
			var edge := exp(-pow((r - 1.0) / 0.035, 2.0)) * (0.65 + 0.35 * sin(a * 3.0 + 1.3))
			var fill: float = 0.12 * clamp(1.0 - r, 0.0, 1.0)
			var alpha: float = clamp(edge * 0.75 + fill, 0.0, 1.0)
			img.set_pixel(x, y, Color(0.22, 0.12, 0.05, alpha))
	return ImageTexture.create_from_image(img)


func _blot_tex(col: Color, strength: float, seed: int, streaks := false) -> ImageTexture:
	# 擦れ・シミ・水あと(ノイズを丸く切り抜いたもの)
	var n := FastNoiseLite.new()
	n.seed = seed
	n.frequency = 0.02
	n.fractal_octaves = 4
	var s := 256
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	for y in s:
		for x in s:
			var d := Vector2(x - s / 2.0, y - s / 2.0) / (s * 0.5)
			var fall: float = clamp(1.0 - d.length(), 0.0, 1.0)
			var v := n.get_noise_2d(x * (0.3 if streaks else 1.0), y) * 0.5 + 0.5
			var a: float = clamp((v - 0.45) * 2.5, 0.0, 1.0) * fall * strength
			img.set_pixel(x, y, Color(col.r, col.g, col.b, a))
	return ImageTexture.create_from_image(img)


func _decal(tex: Texture2D, pos: Vector3, size: Vector3, rot := Vector3.ZERO, albedo_mix := 1.0) -> void:
	var d := Decal.new()
	d.texture_albedo = tex
	d.size = size
	d.albedo_mix = albedo_mix
	d.cull_mask = 1
	main.add_child(d)
	d.global_position = pos
	d.rotation = rot


func _add_decals() -> void:
	var ring := _ring_tex()
	var scuff := _blot_tex(Color(0.12, 0.09, 0.07), 0.45, 3, true)
	var stain := _blot_tex(Color(0.10, 0.08, 0.06), 0.35, 11)
	var water := _blot_tex(Color(0.55, 0.56, 0.52), 0.40, 17)
	var grime := _blot_tex(Color(0.30, 0.27, 0.23), 0.30, 29)
	# 机とラウンジのテーブルの輪じみ
	_decal(ring, Vector3(-2.31, 0.76, -2.47), Vector3(0.10, 0.04, 0.10))
	_decal(ring, Vector3(-2.38, 0.76, -2.62), Vector3(0.09, 0.04, 0.09), Vector3(0, 1.2, 0), 0.7)
	_decal(ring, Vector3(5.22, 0.42, 3.80), Vector3(0.10, 0.04, 0.10))
	# 自室の入口の床の擦れ、机の椅子の下の擦れ
	_decal(scuff, Vector3(0.0, 0.0, -0.75), Vector3(1.1, 0.08, 0.9), Vector3(0, 0.3, 0), 0.8)
	_decal(scuff, Vector3(-1.6, 0.0, -2.6), Vector3(1.0, 0.08, 1.0), Vector3(0, 1.1, 0), 0.6)
	# 廊下のカーペットのシミ
	for x in [-4.2, -1.1, 2.0, 5.1]:
		_decal(stain, Vector3(x, 0.008, 0.62 + randf_range(-0.3, 0.3)), Vector3(0.7, 0.06, 0.7), Vector3(0, randf() * TAU, 0), 0.7)
	# シャワーの床と壁の水あと
	for x in [-6.43, -5.53, -4.63]:
		_decal(water, Vector3(x, 0.0, 4.9), Vector3(0.9, 0.06, 0.9), Vector3(0, randf() * TAU, 0), 0.6)
	_decal(water, Vector3(-6.6, 0.95, 2.8), Vector3(0.9, 0.5, 0.06), Vector3(deg_to_rad(90), 0, 0), 0.4)
	# 照明のスイッチのまわりの手あか(入口の壁)
	_decal(grime, Vector3(0.62, 1.22, -0.36), Vector3(0.22, 0.06, 0.28), Vector3(deg_to_rad(-90), 0, 0), 0.6)
