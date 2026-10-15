extends Node
## 部屋での暮らし: 今日のこと(デイリー)、コーヒー、金魚、水やり、天井の照明、雨、カレンダー、眠る、写真。
## room_setup.gd から action_for() / action_label() / do_action() が呼ばれる。
## 記録は user://life_state.json。集中の記録は focus_mode.gd の user://focus_log.json を読む。

const STATE_PATH := "user://life_state.json"
const TASKS := [
	["focus2", "集中を2回する"],
	["water", "植物に水をやる"],
	["fish", "金魚にえさをやる"],
	["coffee", "コーヒーを1杯飲みきる"],
	["music", "レコードを1曲最後まで聴く"],
	["sleep", "明かりを全部消してから眠る"],
	["shower", "シャワーを浴びる"],
]
const PLANTS := ["ph_bigplant", "ph_sillplant1", "ph_sillplant2", "ph_sillplant3", "ph_shelfplant", "ph_deskplant",
		"ph_cabplant", "wd_hangingplant"]
const INK := Color(0.95, 0.91, 0.84)
const SUB := Color(0.95, 0.91, 0.84, 0.62)
const ACCENT := Color(0.89, 0.63, 0.38)
const PAPER_INK := Color(0.16, 0.14, 0.12)

@onready var main: Node = get_parent()
var player: CharacterBody3D
var focus: Node
var state := {"days": {}, "streak": 0, "streak_last": ""}

# コーヒー
var coffee_sips := 0
var _coffee: Node3D
var _coffee_top := 0.0
var _steam: GPUParticles3D
# 金魚
var _fish: Node3D
var _bowl_c := Vector3.ZERO
var _fish_a := 0.0
var _feed_t := 0.0
var _flakes: Array[MeshInstance3D] = []
# じょうろ
var holding_can := false
var _can: Node3D
var _can_home: Transform3D
var _can_parent: Node
var _spray: GPUParticles3D
# 天井の照明
var ceiling_on := false
var _ceiling_light: OmniLight3D
# 雨
var raining := false
var _rain: GPUParticles3D
var _rain_audio: AudioStreamPlayer
var _env: Environment
var _sky_base := 1.0
# 表示
var _ui: CanvasLayer
var _toasts: VBoxContainer
var _journal: PanelContainer
var _j_title: Label
var _j_list: Label
var _j_stats: Label
var _fade: ColorRect
var _sleep_text: Label
var _hold_hint: Label
var _cal_vp: SubViewport
var _cal_root: Control
var _poll := 0.0
var _plant_nodes := {}


func _ready() -> void:
	player = main.get_node("Player")
	focus = main.get_node_or_null("FocusMode")
	_load()
	_build_ui()
	_setup_coffee()
	_setup_fish()
	_setup_can()
	_setup_ceiling()
	_setup_rain()
	_setup_calendar()
	for pid in PLANTS:
		var pn = main._find(_plant_name(pid))
		if pn:
			_plant_nodes[pid] = pn
	_refresh_journal()


func _process(delta: float) -> void:
	_update_fish(delta)
	_poll -= delta
	if _poll <= 0.0:
		_poll = 2.0
		_check_focus_task()


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var handled := true
	match event.physical_keycode:
		KEY_TAB:
			_journal.visible = not _journal.visible
			_refresh_journal()
		KEY_P:
			_take_photo()
		KEY_Q:
			if holding_can:
				_put_can()
			else:
				handled = false
		KEY_Z:
			if player._pose_key == "bed_" and not player.locked:
				_sleep()
			else:
				handled = false
		_:
			handled = false
	if handled:
		get_viewport().set_input_as_handled()


# ---------------- 操作(room_setup.gd から呼ばれる) ----------------
func action_for(lower: String) -> String:
	if lower.begins_with("kettle_"):
		return "kettle"
	if lower.begins_with("dp_mug"):
		return "mug"
	if lower.begins_with("fishbowl_"):
		return "fish"
	if lower.begins_with("wall_switch") or lower.begins_with("ceiling_lamp"):
		return "ceiling"
	if lower.begins_with("calendar_") or lower.begins_with("dp_notebook"):
		return "journal"
	if lower.begins_with("wateringcan"):
		return "can"
	if lower.begins_with("win_"):
		return "rain"
	for p in PLANTS:
		if lower.begins_with(p):
			return "plant:" + p
	return ""


func _plant_name(pid: String) -> String:
	# 小文字の ID から実際のノード名へ
	return {"ph_bigplant": "PH_BigPlant", "ph_sillplant1": "PH_SillPlant1", "ph_sillplant2": "PH_SillPlant2",
		"ph_sillplant3": "PH_SillPlant3", "ph_shelfplant": "PH_ShelfPlant", "ph_deskplant": "PH_DeskPlant",
		"ph_cabplant": "PH_CabPlant", "wd_hangingplant": "WD_HangingPlant"}[pid]


## じょうろを持っているとき、視線の先(18° 以内・2.2m 以内)のいちばん近い植物を返す。
## 葉には当たり判定がないので、視線の向きで判定する
func aim_action(cam: Camera3D) -> String:
	if not holding_can:
		return ""
	var best := ""
	var best_d := 99.0
	var fwd := -cam.global_basis.z
	for pid in _plant_nodes:
		var c: Vector3 = (_plant_nodes[pid] as Node3D).global_position + Vector3(0, 0.25, 0)
		var v := c - cam.global_position
		var d := v.length()
		if d < 2.2 and fwd.angle_to(v) < deg_to_rad(18.0) and d < best_d:
			best = pid
			best_d = d
	return ("plant:" + best) if best != "" else ""


func handles(key: String) -> bool:
	return key in ["kettle", "mug", "fish", "ceiling", "journal", "can", "rain"] or key.begins_with("plant:")


func action_label(key: String) -> String:
	if key.begins_with("plant:"):
		if _day().watered.has(key.substr(6)):
			return "今日は水やり済み"
		return "水をやる" if holding_can else "水をやる(先にじょうろを持つ)"
	match key:
		"kettle":
			return "コーヒーを淹れる" if coffee_sips == 0 else "マグにまだコーヒーがあります"
		"mug":
			return ("コーヒーを飲む(残り %d 口)" % coffee_sips) if coffee_sips > 0 else "空のマグ(ケトルで淹れる)"
		"fish":
			return "金魚にえさをやる" if not _day().fed else "金魚を眺める(今日のえさは済み)"
		"ceiling":
			return "天井の照明を消す" if ceiling_on else "天井の照明をつける"
		"journal":
			return "今日のことを見る"
		"can":
			return "じょうろを置く" if holding_can else "じょうろを持つ"
		"rain":
			return "雨をやませる" if raining else "窓の外を雨にする"
	return ""


func do_action(key: String) -> void:
	if key.begins_with("plant:"):
		_water(key.substr(6))
		return
	match key:
		"kettle":
			_brew()
		"mug":
			_sip()
		"fish":
			_feed()
		"ceiling":
			_set_ceiling(not ceiling_on)
		"journal":
			_journal.visible = true
			_refresh_journal()
		"can":
			if holding_can:
				_put_can()
			else:
				_pick_can()
		"rain":
			_set_rain(not raining)


func on_track_finished() -> void:
	_day().tracks = int(_day().get("tracks", 0)) + 1
	_complete("music")


# ---------------- 今日のこと ----------------
func _today() -> String:
	return Time.get_date_string_from_system()


func _day() -> Dictionary:
	var t := _today()
	if not state.days.has(t):
		state.days[t] = {"done": [], "coffee": 0, "tracks": 0, "watered": [], "fed": false}
	return state.days[t]


func _complete(id: String) -> void:
	var d := _day()
	if d.done.has(id):
		_save()
		return
	d.done.append(id)
	var label := ""
	for t in TASKS:
		if t[0] == id:
			label = t[1]
	_toast("達成: %s(%d/%d)" % [label, d.done.size(), TASKS.size()])
	if d.done.size() == TASKS.size():
		var yesterday := Time.get_date_string_from_unix_time(int(Time.get_unix_time_from_system()) - 86400 + Time.get_time_zone_from_system().bias * 60)
		state.streak = int(state.streak) + 1 if state.streak_last == yesterday else 1
		state.streak_last = _today()
		_toast("今日のことを全部終えました。連続 %d 日" % state.streak)
	_save()
	_refresh_journal()
	_draw_calendar()


func _check_focus_task() -> void:
	if focus == null or _day().done.has("focus2"):
		return
	var fd: Dictionary = focus._log.days.get(_today(), {})
	if int(fd.get("count", 0)) >= 2:
		_complete("focus2")


func _focus_minutes(date: String) -> int:
	if focus == null:
		return 0
	return int(focus._log.days.get(date, {}).get("minutes", 0))


func _span(m: int) -> String:
	return ("%d時間%d分" % [m / 60, m % 60]) if m >= 60 else ("%d分" % m)


func _streak_now() -> int:
	var yesterday := Time.get_date_string_from_unix_time(int(Time.get_unix_time_from_system()) - 86400 + Time.get_time_zone_from_system().bias * 60)
	return int(state.streak) if state.streak_last in [_today(), yesterday] else 0


func _refresh_journal() -> void:
	if _journal == null:
		return
	var d := _day()
	_j_title.text = "今日のこと %d/%d" % [d.done.size(), TASKS.size()] + ("　連続 %d 日" % _streak_now() if _streak_now() > 0 else "")
	var lines := PackedStringArray()
	for t in TASKS:
		lines.append(("✓  " if d.done.has(t[0]) else "□  ") + t[1])
	_j_list.text = "\n".join(lines)
	var fd: Dictionary = focus._log.days.get(_today(), {}) if focus else {}
	_j_stats.text = "集中 %s(%d回) ・ コーヒー %d杯 ・ 聴いた曲 %d曲 ・ 水やり %d鉢" % [
		_span(int(fd.get("minutes", 0))), int(fd.get("count", 0)), int(d.coffee), int(d.tracks), d.watered.size()]


# ---------------- コーヒー ----------------
func _setup_coffee() -> void:
	_coffee = main._find("DP_Mug_Coffee")
	if _coffee:
		_coffee_top = _coffee.position.y
		_coffee.visible = false
	_steam = _make_puffs(Color(1, 1, 1, 0.22), 0.05, Vector3(0, 0.06, 0), 2.4, 18)
	var mug = main._find("DP_Mug")
	if mug:
		_steam.global_position = (mug as Node3D).global_position + Vector3(0, 0.1, 0)
	_steam.emitting = false


func _brew() -> void:
	if coffee_sips > 0 or _coffee == null:
		return
	coffee_sips = 3
	_coffee.visible = true
	_coffee.position.y = _coffee_top
	_steam.emitting = true
	_toast("コーヒーを淹れました(机のマグ)")


func _sip() -> void:
	if coffee_sips <= 0:
		return
	coffee_sips -= 1
	_coffee.position.y = _coffee_top - 0.021 * (3 - coffee_sips)
	if coffee_sips == 0:
		_coffee.visible = false
		_steam.emitting = false
		_day().coffee = int(_day().coffee) + 1
		_complete("coffee")


# ---------------- 金魚 ----------------
func _setup_fish() -> void:
	_fish = main._find("Fish_Goldfish")
	var water = main._find("Fishbowl_Water")
	if _fish:
		_fish.scale = Vector3.ONE * 1.6
	if _fish and water:
		_bowl_c = (water as Node3D).global_position


func _update_fish(delta: float) -> void:
	if _fish == null:
		return
	var target: Vector3
	if _feed_t > 0.0:
		_feed_t -= delta
		# えさが浮いている水面の近くへ
		var aim := _bowl_c + Vector3(0.0, 0.125, 0.0)
		if _flakes.size() > 0:
			aim = _flakes[0].global_position + Vector3(0, -0.012, 0)
		target = _fish.global_position.lerp(aim, clamp(delta * 1.5, 0.0, 1.0))
		for f in _flakes.duplicate():
			f.global_position.y -= delta * 0.004
			if f.global_position.distance_to(_fish.global_position) < 0.02:
				_flakes.erase(f)
				f.queue_free()
		if _feed_t <= 0.0:
			for f in _flakes:
				f.queue_free()
			_flakes.clear()
	else:
		_fish_a += delta * 0.55
		var bob := sin(_fish_a * 1.7) * 0.012
		var r := 0.045 + 0.008 * sin(_fish_a * 0.6)
		var aim2 := _bowl_c + Vector3(cos(_fish_a) * r, 0.065 + bob, sin(_fish_a) * r)
		target = _fish.global_position.lerp(aim2, clamp(delta * 3.0, 0.0, 1.0))
	var dir := target - _fish.global_position
	_fish.global_position = target
	if dir.length() > 0.0001:
		var yaw := atan2(-dir.z, dir.x)  # 金魚の体は +X 向きに作ってある
		_fish.rotation.y = lerp_angle(_fish.rotation.y, yaw + sin(Time.get_ticks_msec() / 90.0) * 0.12, clamp(delta * 6.0, 0.0, 1.0))


func _feed() -> void:
	if _fish == null:
		return
	var first: bool = not _day().fed
	_day().fed = true
	_feed_t = 9.0
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.55, 0.33, 0.12)
	mat.roughness = 0.9
	for i in 7:
		var m := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = Vector3(0.006, 0.001, 0.005)
		m.mesh = b
		m.material_override = mat
		add_child(m)
		m.global_position = _bowl_c + Vector3(randf_range(-0.035, 0.035), 0.142, randf_range(-0.035, 0.035))
		m.rotation.y = randf() * TAU
		_flakes.append(m)
	if first:
		_complete("fish")
	else:
		_toast("金魚がえさを食べています")


# ---------------- じょうろと水やり ----------------
func _setup_can() -> void:
	var body = main._find("WateringCan_Body")
	if body == null:
		return
	_can = Node3D.new()
	_can.name = "WateringCanRoot"
	body.get_parent().add_child(_can)
	_can.global_position = (body as Node3D).global_position
	for n in ["WateringCan_Body", "WateringCan_Spout", "WateringCan_Rose", "WateringCan_Handle", "WateringCan_Handle_mesh"]:
		var p = main._find(n)
		if p and p.get_parent() != _can:
			p.reparent(_can, true)
	_can_home = _can.global_transform
	_can_parent = _can.get_parent()
	_spray = _make_drops()
	_can.add_child(_spray)
	_spray.position = Vector3(0.21, 0.18, 0.0)


func _pick_can() -> void:
	if _can == null:
		return
	holding_can = true
	_can.reparent(player.camera, false)
	_can.position = Vector3(0.22, -0.30, -0.55)
	_can.rotation = Vector3(0.0, deg_to_rad(100), 0.0)
	_hold_hint.visible = true


func _put_can() -> void:
	holding_can = false
	_can.reparent(_can_parent, false)
	_can.global_transform = _can_home
	_hold_hint.visible = false


func _water(plant: String) -> void:
	if not holding_can:
		_toast("先にじょうろを持ってください(棚の横の床)")
		return
	if _day().watered.has(plant):
		_toast("この鉢は今日はもう水やり済みです")
		return
	var tw := create_tween()
	tw.tween_property(_can, "rotation:z", deg_to_rad(-35), 0.35)
	tw.tween_callback(func(): _spray.emitting = true)
	tw.tween_interval(1.1)
	tw.tween_callback(func(): _spray.emitting = false)
	tw.tween_property(_can, "rotation:z", 0.0, 0.35)
	_day().watered.append(plant)
	var first: bool = not _day().done.has("water")
	if first:
		_complete("water")
	else:
		_toast("水やり %d/%d 鉢" % [_day().watered.size(), PLANTS.size()])
		_save()


# ---------------- 天井の照明 ----------------
func _setup_ceiling() -> void:
	var bulb = main._find("Ceiling_Lamp_Bulb")
	if bulb == null:
		return
	_ceiling_light = OmniLight3D.new()
	_ceiling_light.light_color = Color(1.0, 0.84, 0.66)
	_ceiling_light.light_energy = 2.4
	_ceiling_light.omni_range = 6.5
	_ceiling_light.omni_attenuation = 1.1
	_ceiling_light.shadow_enabled = true
	_ceiling_light.light_volumetric_fog_energy = 0.3
	main.add_child(_ceiling_light)
	_ceiling_light.global_position = (bulb as Node3D).global_position + Vector3(0, -0.03, 0)
	_ceiling_light.visible = false
	for n in ["Ceiling_Lamp_Bulb", "Ceiling_Lamp_Shade"]:
		var mi = main._find(n)
		if mi is GeometryInstance3D:
			mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
			# オパールガラスのシェードは光を通すので影を落とさない(壁に波打つ境目が出るため)
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _set_ceiling(on: bool) -> void:
	ceiling_on = on
	if _ceiling_light:
		_ceiling_light.visible = on
	for pair in [["Ceiling_Lamp_Bulb", 6.0], ["Ceiling_Lamp_Shade", 1.4]]:
		var mi = main._find(pair[0])
		if mi is MeshInstance3D:
			var m: Material = mi.get_surface_override_material(0)
			if m == null:
				m = mi.get_active_material(0).duplicate()
				mi.set_surface_override_material(0, m)
			if m is StandardMaterial3D:
				m.emission_enabled = on
				m.emission = Color(1.0, 0.78, 0.55)
				m.emission_energy_multiplier = pair[1]


func lights_all_off() -> bool:
	return not ceiling_on and not main.desk_lamp_on and not main.globe_on and not main.monitor_on


# ---------------- 雨 ----------------
func _setup_rain() -> void:
	_env = main.get_node("WorldEnvironment").environment
	if _env.sky and _env.sky.sky_material is PanoramaSkyMaterial:
		_sky_base = (_env.sky.sky_material as PanoramaSkyMaterial).energy_multiplier
	_rain = GPUParticles3D.new()
	_rain.amount = 1800
	_rain.lifetime = 0.9
	_rain.visibility_aabb = AABB(Vector3(-4, -6, -4), Vector3(8, 10, 8))
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(2.8, 0.2, 2.0)
	pm.direction = Vector3(0.05, -1, 0)
	pm.spread = 2.0
	pm.initial_velocity_min = 7.0
	pm.initial_velocity_max = 8.5
	pm.gravity = Vector3(0, -2, 0)
	_rain.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.006, 0.32)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = Color(0.82, 0.86, 0.92, 0.32)
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	q.material = mat
	_rain.draw_pass_1 = q
	_rain.emitting = false
	main.add_child(_rain)
	_rain.global_position = Vector3(0.3, 4.2, -7.4)  # 窓の外(奥の壁の向こう)
	_rain_audio = AudioStreamPlayer.new()
	var st: AudioStreamWAV = load("res://assets/sounds/rain.wav")
	st.loop_mode = AudioStreamWAV.LOOP_FORWARD
	st.loop_begin = 0
	st.loop_end = int(st.get_length() * st.mix_rate)
	_rain_audio.stream = st
	_rain_audio.volume_db = -60.0
	add_child(_rain_audio)


func _set_rain(on: bool) -> void:
	raining = on
	_rain.emitting = on
	if on:
		_rain_audio.play()
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_rain_audio, "volume_db", -9.0 if on else -60.0, 2.5)
	# 空の明るさと太陽・月は World が昼夜・カーテンと合わせて決める
	var w: Node = main.get_node_or_null("World")
	if w:
		w.refresh_light(2.5)
	if not on:
		tw.chain().tween_callback(func(): if not raining: _rain_audio.stop())
	_toast("窓の外が雨になりました" if on else "雨がやみました")


# ---------------- カレンダー ----------------
func _setup_calendar() -> void:
	_cal_vp = SubViewport.new()
	_cal_vp.size = Vector2i(600, 840)
	_cal_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(_cal_vp)
	_cal_root = Control.new()
	_cal_root.size = Vector2(600, 840)
	_cal_vp.add_child(_cal_root)
	var page = main._find("Calendar_Page")
	if page is MeshInstance3D:
		var m := StandardMaterial3D.new()
		m.albedo_texture = _cal_vp.get_texture()
		m.roughness = 0.85
		# 右の壁の内側から見て左右が逆になるので反転する
		m.uv1_scale = Vector3(-1, 1, 1)
		m.uv1_offset = Vector3(1, 0, 0)
		page.set_surface_override_material(0, m)
	_draw_calendar()


func _draw_calendar() -> void:
	if _cal_root == null:
		return
	for c in _cal_root.get_children():
		c.queue_free()
	var bg := ColorRect.new()
	bg.color = Color(0.93, 0.91, 0.87)
	bg.size = Vector2(600, 840)
	_cal_root.add_child(bg)
	var now := Time.get_datetime_dict_from_system()
	var y: int = now.year
	var mo: int = now.month
	_text("%d年%d月" % [y, mo], Vector2(40, 34), 46, PAPER_INK)
	var heads := ["日", "月", "火", "水", "木", "金", "土"]
	for i in 7:
		var col := Color(0.62, 0.22, 0.14) if i == 0 else (Color(0.20, 0.32, 0.55) if i == 6 else Color(PAPER_INK, 0.7))
		_text(heads[i], Vector2(40 + i * 76 + 26, 120), 22, col)
	var first := Time.get_unix_time_from_datetime_dict({"year": y, "month": mo, "day": 1, "hour": 12})
	var wd: int = Time.get_datetime_dict_from_unix_time(first).weekday
	var days_in: int = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
	var month_min := 0
	for d in range(1, days_in + 1):
		var idx: int = wd + d - 1
		var pos := Vector2(40 + (idx % 7) * 76, 160 + int(idx / 7) * 96)
		var date := "%04d-%02d-%02d" % [y, mo, d]
		var mins := _focus_minutes(date)
		month_min += mins
		if mins > 0:
			var stamp := Panel.new()
			var sb := StyleBoxFlat.new()
			sb.bg_color = Color(0.89, 0.63, 0.38, 0.45) if mins < 60 else (Color(0.80, 0.45, 0.20, 0.7) if mins < 120 else Color(0.62, 0.24, 0.10, 0.85))
			sb.set_corner_radius_all(30)
			stamp.add_theme_stylebox_override("panel", sb)
			stamp.position = pos + Vector2(10, 22)
			stamp.size = Vector2(56, 56)
			_cal_root.add_child(stamp)
		if date == _today():
			var ring := Panel.new()
			var rb := StyleBoxFlat.new()
			rb.bg_color = Color(0, 0, 0, 0)
			rb.border_color = PAPER_INK
			rb.set_border_width_all(3)
			rb.set_corner_radius_all(8)
			ring.add_theme_stylebox_override("panel", rb)
			ring.position = pos + Vector2(2, 0)
			ring.size = Vector2(72, 88)
			_cal_root.add_child(ring)
		_text(str(d), pos + Vector2(10, 4), 20, PAPER_INK)
		var dd: Dictionary = state.days.get(date, {})
		if dd.get("done", []).size() == TASKS.size():
			_text("✓", pos + Vector2(48, 50), 24, Color(0.25, 0.42, 0.26))
	_text("今月の集中 %s　連続 %d 日" % [_span(month_min), _streak_now()], Vector2(40, 784), 24, Color(PAPER_INK, 0.8))
	_cal_vp.render_target_update_mode = SubViewport.UPDATE_ONCE


func _text(s: String, pos: Vector2, size: int, col: Color) -> Label:
	var l := Label.new()
	l.text = s
	l.position = pos
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	_cal_root.add_child(l)
	return l


# ---------------- 眠る ----------------
func _sleep() -> void:
	var all_off := lights_all_off()
	if all_off:
		_complete("sleep")
	var d := _day()
	var fd: Dictionary = focus._log.days.get(_today(), {}) if focus else {}
	_sleep_text.text = "今日のまとめ\n\n集中 %s(%d回)\nコーヒー %d杯 ・ 聴いた曲 %d曲\n水やり %d鉢 ・ 金魚のえさ %s\n今日のこと %d/%d%s" % [
		_span(int(fd.get("minutes", 0))), int(fd.get("count", 0)), int(d.coffee), int(d.tracks), d.watered.size(),
		"済み" if d.fed else "まだ", d.done.size(), TASKS.size(),
		"" if all_off else "\n\n明かりがついたままでした"]
	_fade.visible = true
	_fade.modulate.a = 0.0
	_sleep_text.modulate.a = 0.0
	if main.playing:
		main._stop()
	var tw := create_tween()
	tw.tween_property(_fade, "modulate:a", 1.0, 1.6)
	tw.tween_property(_sleep_text, "modulate:a", 1.0, 0.8)
	tw.tween_interval(4.0)
	tw.tween_property(_sleep_text, "modulate:a", 0.0, 0.8)
	tw.tween_property(_fade, "modulate:a", 0.0, 1.8)
	tw.tween_callback(func(): _fade.visible = false)


# ---------------- 写真 ----------------
func _take_photo() -> void:
	var layers: Array = []
	for n in main.get_children():
		if n is CanvasLayer and n.visible:
			layers.append(n)
	if _ui.visible:
		layers.append(_ui)
	for l in layers:
		l.visible = false
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	for l in layers:
		l.visible = true
	var dir := OS.get_system_dir(OS.SYSTEM_DIR_PICTURES).path_join("DormRoom")
	DirAccess.make_dir_recursive_absolute(dir)
	var fname := "dorm_%s.png" % Time.get_datetime_string_from_system().replace(":", "").replace("-", "").replace("T", "_")
	img.save_png(dir.path_join(fname))
	_toast("写真を保存しました: ピクチャ/DormRoom/%s" % fname)


# ---------------- 保存 ----------------
func _save() -> void:
	var f := FileAccess.open(STATE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(state, "  "))


func _load() -> void:
	if FileAccess.file_exists(STATE_PATH):
		var data = JSON.parse_string(FileAccess.get_file_as_string(STATE_PATH))
		if data is Dictionary and data.has("days"):
			state = data


# ---------------- 表示の部品 ----------------
func _toast(msg: String) -> void:
	var p := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.06, 0.05, 0.78)
	sb.set_corner_radius_all(8)
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 8
	sb.content_margin_bottom = 8
	p.add_theme_stylebox_override("panel", sb)
	var l := Label.new()
	l.text = msg
	l.add_theme_font_size_override("font_size", 17)
	l.add_theme_color_override("font_color", INK)
	p.add_child(l)
	_toasts.add_child(p)
	p.modulate.a = 0.0
	var tw := p.create_tween()
	tw.tween_property(p, "modulate:a", 1.0, 0.25)
	tw.tween_interval(3.2)
	tw.tween_property(p, "modulate:a", 0.0, 0.6)
	tw.tween_callback(p.queue_free)


func _build_ui() -> void:
	_ui = CanvasLayer.new()
	_ui.layer = 5
	add_child(_ui)
	_toasts = VBoxContainer.new()
	_toasts.anchor_left = 0.5
	_toasts.anchor_right = 0.5
	_toasts.anchor_top = 1.0
	_toasts.anchor_bottom = 1.0
	_toasts.offset_left = -300
	_toasts.offset_right = 300
	_toasts.offset_top = -230
	_toasts.offset_bottom = -100
	_toasts.alignment = BoxContainer.ALIGNMENT_END
	_toasts.add_theme_constant_override("separation", 6)
	_ui.add_child(_toasts)

	_hold_hint = Label.new()
	_hold_hint.text = "じょうろを持っています(植物を見て E: 水をやる / Q: じょうろを置く)"
	_hold_hint.add_theme_font_size_override("font_size", 15)
	_hold_hint.add_theme_color_override("font_color", SUB)
	_hold_hint.anchor_top = 1.0
	_hold_hint.anchor_bottom = 1.0
	_hold_hint.offset_left = 20
	_hold_hint.offset_top = -40
	_hold_hint.visible = false
	_ui.add_child(_hold_hint)

	_journal = PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.93, 0.90, 0.84, 0.96)
	sb.set_corner_radius_all(6)
	sb.content_margin_left = 34
	sb.content_margin_right = 34
	sb.content_margin_top = 26
	sb.content_margin_bottom = 26
	_journal.add_theme_stylebox_override("panel", sb)
	_journal.anchor_left = 0.5
	_journal.anchor_right = 0.5
	_journal.anchor_top = 0.5
	_journal.anchor_bottom = 0.5
	_journal.offset_left = -270
	_journal.offset_right = 270
	_journal.offset_top = -210
	_journal.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_journal.grow_vertical = Control.GROW_DIRECTION_BOTH
	_ui.add_child(_journal)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 14)
	_journal.add_child(v)
	_j_title = _label(v, 24, PAPER_INK)
	_j_list = _label(v, 19, PAPER_INK)
	_j_list.add_theme_constant_override("line_spacing", 6)
	_j_stats = _label(v, 15, Color(PAPER_INK, 0.7))
	_j_stats.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_j_stats.custom_minimum_size = Vector2(470, 0)
	var close := _label(v, 13, Color(PAPER_INK, 0.5))
	close.text = "Tab: 閉じる"
	_journal.visible = false

	var top := CanvasLayer.new()
	top.layer = 20
	add_child(top)
	_fade = ColorRect.new()
	_fade.color = Color(0.01, 0.01, 0.015)
	_fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade.visible = false
	top.add_child(_fade)
	_sleep_text = Label.new()
	_sleep_text.set_anchors_preset(Control.PRESET_FULL_RECT)
	_sleep_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_sleep_text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_sleep_text.add_theme_font_size_override("font_size", 24)
	_sleep_text.add_theme_color_override("font_color", INK)
	_sleep_text.add_theme_constant_override("line_spacing", 8)
	_fade.add_child(_sleep_text)


func _label(parent: Node, size: int, col: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	parent.add_child(l)
	return l


func _soft_tex() -> GradientTexture2D:
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(0.5, 0.0)
	t.width = 64
	t.height = 64
	return t


func _make_puffs(col: Color, size: float, vel: Vector3, life: float, amount: int) -> GPUParticles3D:
	"""湯気のようなやわらかい粒"""
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = life
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 0.018
	pm.direction = vel.normalized()
	pm.spread = 14.0
	pm.initial_velocity_min = vel.length() * 0.6
	pm.initial_velocity_max = vel.length()
	pm.gravity = Vector3(0, 0.012, 0)
	pm.scale_min = 0.6
	pm.scale_max = 1.4
	var curve := Curve.new()
	curve.add_point(Vector2(0, 0.4))
	curve.add_point(Vector2(1, 1.6))
	var ct := CurveTexture.new()
	ct.curve = curve
	pm.scale_curve = ct
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 0))
	g.add_point(0.25, Color(1, 1, 1, 1))
	g.set_color(g.get_point_count() - 1, Color(1, 1, 1, 0))
	var gt := GradientTexture1D.new()
	gt.gradient = g
	pm.color_ramp = gt
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.vertex_color_use_as_albedo = true
	m.albedo_color = col
	m.albedo_texture = _soft_tex()
	q.material = m
	p.draw_pass_1 = q
	add_child(p)
	return p


func _make_drops() -> GPUParticles3D:
	"""じょうろから出る水"""
	var p := GPUParticles3D.new()
	p.amount = 120
	p.lifetime = 0.7
	p.emitting = false
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 0.012
	pm.direction = Vector3(1, -0.4, 0)
	pm.spread = 12.0
	pm.initial_velocity_min = 0.6
	pm.initial_velocity_max = 1.0
	pm.gravity = Vector3(0, -6, 0)
	p.process_material = pm
	var s := SphereMesh.new()
	s.radius = 0.0035
	s.height = 0.009
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.75, 0.85, 0.95, 0.6)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.roughness = 0.05
	s.material = m
	p.draw_pass_1 = s
	return p
