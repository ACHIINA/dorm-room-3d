extends Node
## 寮の共用部と隣の部屋: 315 号室とシャワールームのドア、ほかの部屋へのノック、
## ラウンジのテレビ・ソファ・電子レンジ、シャワー、各部屋の照明と鏡の映り込み。
## room_setup.gd から action_for() / action_label() / do_action() が呼ばれる。

const KNOCK_REPLIES := ["(返事がない。留守のようだ)", "「今ちょっと手が離せない!あとでね」", "「はーい…あ、部屋まちがえてない?」",
	"(中から音楽が聞こえる)", "「どうぞー!…って誰もいなかった?」"]
const TV_DIR := "res://assets/tv"

@onready var main: Node = get_parent()
var player: CharacterBody3D
var life: Node

# 開くドア: キー → {pivot, open(bool), angle(開いたときの回転), label}
var doors := {}
var _knock: AudioStreamPlayer3D
# テレビ
var tv_on := false
var _tv_vp: SubViewport
var _tv_rects: Array[TextureRect] = []
var _tv_imgs: Array[Texture2D] = []
var _tv_i := 0
var _tv_t := 0.0
var _tv_light: OmniLight3D
var _tv_screen: MeshInstance3D
# 電子レンジ
var _mw_left := 0.0
var _mw_light: OmniLight3D
var _ding: AudioStreamPlayer3D
# シャワー
var showers := {}   # i → {on, curtain, water, steam, audio}


func _ready() -> void:
	player = main.get_node("Player")
	life = main.get_node_or_null("Life")
	_setup_door("door315", "Hall_Door315_", 1.75, "315号室のドア")
	_setup_door("doorshower", "Hall_DoorSHOWERS_", -1.75, "シャワールームのドア")
	_knock = AudioStreamPlayer3D.new()
	_knock.stream = load("res://assets/sounds/knock.wav")
	_knock.unit_size = 3.0
	main.add_child(_knock)
	_setup_lights()
	_setup_tv()
	_setup_microwave()
	_setup_showers()
	_setup_probes()
	# ソファに座る姿勢(テレビの方を向く)
	player.POSES["lounge_sofa"] = {"label": "ソファに座る", "head": Vector3(4.05, 1.02, 4.10), "yaw": -PI / 2, "pitch": -0.05}


func _process(delta: float) -> void:
	if tv_on and _tv_imgs.size() > 1:
		_tv_t += delta
		var fade: float = clamp((_tv_t - 6.0) / 1.2, 0.0, 1.0)
		_tv_rects[1].modulate.a = fade
		if _tv_t >= 7.2:
			_tv_t = 0.0
			_tv_i = (_tv_i + 1) % _tv_imgs.size()
			_tv_rects[0].texture = _tv_imgs[_tv_i]
			_tv_rects[1].texture = _tv_imgs[(_tv_i + 1) % _tv_imgs.size()]
			_tv_rects[1].modulate.a = 0.0
		_tv_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	if _mw_left > 0.0:
		_mw_left -= delta
		if _mw_left <= 0.0:
			_mw_light.visible = false
			_ding.play()
			if life:
				life._toast("電子レンジ: 温まりました")


# ---------------- 操作 ----------------
func action_for(lower: String) -> String:
	if lower.begins_with("hall_door315_"):
		return "door315"
	if lower.begins_with("hall_doorshowers_"):
		return "doorshower"
	for n in ["311", "312", "314", "317"]:
		if lower.begins_with("hall_door%s_" % n):
			return "knock:" + n
	if lower.begins_with("lounge_tv"):
		return "tv"
	if lower.begins_with("lounge_microwave"):
		return "microwave"
	if lower.begins_with("shower_curtain") or lower.begins_with("shower_head") or lower.begins_with("shower_valve") or lower.begins_with("shower_arm"):
		# 名前の最初の数字がブースの番号(shower_curtain0 など)
		for c in lower:
			if c.is_valid_int():
				return "shower:" + c
		return ""
	return ""


func handles(key: String) -> bool:
	return key in ["door315", "doorshower", "tv", "microwave"] or key.begins_with("knock:") or key.begins_with("shower:")


func action_label(key: String) -> String:
	if doors.has(key):
		return doors[key].label + ("を閉める" if doors[key].open else "を開ける")
	if key.begins_with("knock:"):
		return "ノックする(%s号室)" % key.substr(6)
	if key.begins_with("shower:"):
		var s = showers.get(int(key.substr(7)))
		return "シャワーを止める" if s and s.on else "シャワーを浴びる"
	match key:
		"tv":
			return "テレビを消す" if tv_on else "テレビをつける"
		"microwave":
			return ("電子レンジ: 残り %d 秒" % int(ceil(_mw_left))) if _mw_left > 0.0 else "電子レンジで温める(30秒)"
	return ""


func do_action(key: String) -> void:
	if doors.has(key):
		_set_door(key, not doors[key].open)
		return
	if key.begins_with("knock:"):
		_knock_door(key.substr(6))
		return
	if key.begins_with("shower:"):
		_toggle_shower(int(key.substr(7)))
		return
	match key:
		"tv":
			_set_tv(not tv_on)
		"microwave":
			if _mw_left <= 0.0:
				_mw_left = 30.0
				_mw_light.visible = true


# ---------------- ドアとノック ----------------
func _setup_door(key: String, prefix: String, angle: float, label: String) -> void:
	var slab = main._find(prefix + "Slab")
	if slab == null:
		return
	var aabb: AABB = (slab as MeshInstance3D).get_aabb()
	var lo: Vector3 = slab.global_transform * aabb.position
	var pivot := Node3D.new()
	pivot.name = key + "_pivot"
	main.add_child(pivot)
	# 蝶番はレバーの反対側(-X の端)
	pivot.global_position = Vector3(lo.x, 0.0, (slab as Node3D).global_position.z)
	for part in ["Slab", "Rose", "LeverNeck", "Lever"]:
		var p = main._find(prefix + part)
		if p:
			p.reparent(pivot, true)
	doors[key] = {"pivot": pivot, "open": false, "angle": angle, "label": label}


func _set_door(key: String, open: bool) -> void:
	var d: Dictionary = doors[key]
	d.open = open
	var tw := create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(d.pivot, "rotation:y", d.angle if open else 0.0, 1.1)


func _knock_door(n: String) -> void:
	var slab = main._find("Hall_Door%s_Slab" % n)
	if slab:
		_knock.global_position = (slab as Node3D).global_position
	_knock.play()
	var reply: String = KNOCK_REPLIES[randi() % KNOCK_REPLIES.size()]
	get_tree().create_timer(1.4).timeout.connect(func(): if life: life._toast("%s号室: %s" % [n, reply]))


# ---------------- 照明と映り込み ----------------
func _omni(pos: Vector3, color: Color, energy: float, rng: float, shadow := false) -> OmniLight3D:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = rng
	l.omni_attenuation = 1.3
	l.shadow_enabled = shadow
	l.light_volumetric_fog_energy = 0.15
	main.add_child(l)
	l.global_position = pos
	return l


func _setup_lights() -> void:
	var cool := Color(0.95, 0.97, 1.0)
	var warm := Color(1.0, 0.72, 0.42)
	for i in 3:
		var p = main._find("Lounge_Light_%d" % i)
		if p:
			_omni((p as Node3D).global_position + Vector3(0, -0.25, 0), cool, 0.85, 4.5, i == 1)
	for i in 2:
		var p = main._find("Shower_Light_%d" % i)
		if p:
			_omni((p as Node3D).global_position + Vector3(0, -0.25, 0), cool, 1.1, 3.8, i == 0)
	var lamp = main._find("Lounge_FloorLamp_Shade")
	if lamp:
		_omni((lamp as Node3D).global_position + Vector3(0, 0.12, 0), warm, 0.9, 3.0, true)
	# 315 号室: 天井の照明(控えめ)とガーランドライト
	var cl = main._find("R315_CeilingLight")
	if cl:
		_omni((cl as Node3D).global_position + Vector3(0, -0.3, 0), Color(1.0, 0.80, 0.60), 0.28, 4.0, true)  # 夜はガーランドライトが主役
	for i in [2, 6, 10]:
		var b = main._find("R315_Fairy_%d" % i)
		if b:
			_omni((b as Node3D).global_position + Vector3(0, -0.05, 0.08), warm, 0.45, 2.4)


func _setup_probes() -> void:
	# 鏡と床の映り込み用(シャワールームとラウンジ)
	for spec in [[Vector3(-5.49, 1.27, 3.56), Vector3(2.9, 2.6, 3.8)], [Vector3(4.1, 1.35, 3.96), Vector3(5.7, 2.7, 4.6)]]:
		var p := ReflectionProbe.new()
		p.size = spec[1]
		p.box_projection = true
		p.interior = true
		p.update_mode = ReflectionProbe.UPDATE_ONCE
		main.add_child(p)
		p.global_position = spec[0]


# ---------------- テレビ ----------------
func _setup_tv() -> void:
	_tv_screen = main._find("Lounge_TV_Screen")
	var d := DirAccess.open(TV_DIR)
	if d:
		for f in d.get_files():
			if f.ends_with(".jpg") or f.ends_with(".png"):
				var t = load(TV_DIR.path_join(f))
				if t is Texture2D:
					_tv_imgs.append(t)
	_tv_vp = SubViewport.new()
	_tv_vp.size = Vector2i(960, 540)
	_tv_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(_tv_vp)
	var bg := ColorRect.new()
	bg.color = Color.BLACK
	bg.size = Vector2(960, 540)
	_tv_vp.add_child(bg)
	for i in 2:
		var r := TextureRect.new()
		r.size = Vector2(960, 540)
		r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		r.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		if _tv_imgs.size() > i:
			r.texture = _tv_imgs[i]
		_tv_vp.add_child(r)
		_tv_rects.append(r)
	_tv_rects[1].modulate.a = 0.0
	if _tv_screen:
		_tv_light = _omni(_tv_screen.global_position + Vector3(-0.6, 0, 0), Color(0.75, 0.82, 0.95), 0.6, 3.0)
		_tv_light.visible = false


func _set_tv(on: bool) -> void:
	tv_on = on
	if _tv_screen == null:
		return
	if on:
		var m := StandardMaterial3D.new()
		m.albedo_texture = _tv_vp.get_texture()
		m.emission_enabled = true
		m.emission_texture = _tv_vp.get_texture()
		m.emission_energy_multiplier = 1.2
		m.roughness = 0.15
		# 東の壁(-X 向き)に貼ってあるので左右を反転する
		m.uv1_scale = Vector3(-1, 1, 1)
		m.uv1_offset = Vector3(1, 0, 0)
		_tv_screen.set_surface_override_material(0, m)
		_tv_t = 0.0
	else:
		_tv_screen.set_surface_override_material(0, null)
	_tv_light.visible = on


# ---------------- 電子レンジ ----------------
func _setup_microwave() -> void:
	var mw = main._find("Lounge_Microwave")
	_ding = AudioStreamPlayer3D.new()
	_ding.stream = load("res://assets/sounds/chime.wav")
	_ding.unit_size = 2.0
	main.add_child(_ding)
	_mw_light = _omni(Vector3.ZERO, Color(1.0, 0.8, 0.5), 0.25, 0.9)
	_mw_light.visible = false
	if mw:
		_mw_light.global_position = (mw as Node3D).global_position + Vector3(0.1, 0, 0)
		_ding.global_position = (mw as Node3D).global_position


# ---------------- シャワー ----------------
func _setup_showers() -> void:
	var rain: AudioStreamWAV = load("res://assets/sounds/rain.wav")
	for i in 3:
		var cur = main._find("Shower_Curtain%d" % i)
		var head = main._find("Shower_Head%d" % i)
		if cur == null or head == null:
			continue
		var water := GPUParticles3D.new()
		water.amount = 260
		water.lifetime = 0.55
		water.emitting = false
		var pm := ParticleProcessMaterial.new()
		pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
		pm.emission_sphere_radius = 0.035
		pm.direction = Vector3(0, -1, -0.15)
		pm.spread = 12.0
		pm.initial_velocity_min = 2.2
		pm.initial_velocity_max = 2.8
		pm.gravity = Vector3(0, -9.8, 0)
		water.process_material = pm
		var q := QuadMesh.new()
		q.size = Vector2(0.004, 0.09)
		var qm := StandardMaterial3D.new()
		qm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		qm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		qm.albedo_color = Color(0.85, 0.9, 0.95, 0.45)
		qm.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
		q.material = qm
		water.draw_pass_1 = q
		main.add_child(water)
		water.global_position = (head as Node3D).global_position + Vector3(0, -0.03, 0)
		var steam: GPUParticles3D = life._make_puffs(Color(1, 1, 1, 0.12), 0.35, Vector3(0, 0.25, 0), 4.0, 24) if life else null
		if steam:
			steam.reparent(main, false)
			steam.global_position = (head as Node3D).global_position + Vector3(0, -1.2, -0.3)
			steam.emitting = false
		var au := AudioStreamPlayer3D.new()
		au.stream = rain
		au.unit_size = 2.5
		au.volume_db = -6.0
		main.add_child(au)
		au.global_position = (head as Node3D).global_position
		showers[i] = {"on": false, "curtain": cur, "water": water, "steam": steam, "audio": au, "open_x": (cur as Node3D).scale.x}


func _toggle_shower(i: int) -> void:
	if not showers.has(i):
		return
	var s: Dictionary = showers[i]
	s.on = not s.on
	s.water.emitting = s.on
	if s.steam:
		s.steam.emitting = s.on
	if s.on:
		s.audio.play()
		if life:
			life._complete("shower")
	else:
		s.audio.stop()
	# 浴びるときはカーテンを閉め、止めたら開ける
	var tw := create_tween().set_trans(Tween.TRANS_SINE)
	tw.tween_property(s.curtain, "scale:x", 1.0 if s.on else s.open_x, 0.8)
