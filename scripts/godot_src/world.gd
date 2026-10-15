extends Node
## 昼と夜、部屋のドアの開け閉め、廊下の照明。
## 窓から入る光(太陽・月・窓の明るさ・空)は、昼夜・カーテン・雨の状態から refresh_light() でまとめて決める。
## 起動時は実際の時刻(6:00〜17:59 は昼)。T キーか目覚まし時計で切り替え。

const DAY_SKY := "res://assets/sky/cambridge.jpg"   # 昼の窓の外(ケンブリッジの大学の中庭)
const DAY_ROT := 4.71                                # 芝生の中庭と校舎が窓の正面に来る向き
const DAY_SKY_ENERGY := 1.0
const SUN_ENERGY := 1.1   # 曇り空なので直射は控えめ
const WIN_DAY := {"energy": 3.2, "color": Color(0.92, 0.95, 1.0)}   # 窓からの拡散光
const AMB_DAY := {"color": Color(0.74, 0.76, 0.80), "energy": 0.55}
const EXPOSURE_DAY := 1.05
const FOG_DAY := 0.025

var is_day := false
var door_open := true

@onready var main: Node = get_parent()
var env: Environment
var sky_mat: PanoramaSkyMaterial
var sun: DirectionalLight3D
var _night := {}
var _day_tex: Texture2D
var _door: Node3D
var _door_open_y := 0.0


func _ready() -> void:
	env = main.get_node("WorldEnvironment").environment
	sky_mat = env.sky.sky_material
	var moon: DirectionalLight3D = main.get_node("Moon")
	var win: Light3D = main.get_node("WindowSky")
	_night = {"tex": sky_mat.panorama, "rot": env.sky_rotation.y, "sky": sky_mat.energy_multiplier,
		"moon": moon.light_energy, "win": win.light_energy, "win_color": win.light_color,
		"amb_color": env.ambient_light_color, "amb": env.ambient_light_energy,
		"exposure": env.tonemap_exposure, "fog": env.volumetric_fog_density}
	_day_tex = load(DAY_SKY)
	# 太陽: 窓から斜め下へ。月と同じく影を落とす
	sun = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.94, 0.85)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 15.0
	sun.light_volumetric_fog_energy = 1.5
	main.add_child(sun)
	sun.look_at_from_position(Vector3(0, 4, -6), Vector3(0, 4, -6) + Vector3(0.25, -0.9, 1.0), Vector3.UP)
	sun.visible = false
	sun.light_energy = 0.0
	_door = main._find("Door_Leaf")
	if _door:
		_door_open_y = _door.rotation.y
	_setup_hall_lights()
	var h: int = Time.get_datetime_dict_from_system().hour
	set_day(h >= 6 and h < 18, true)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == KEY_T:
		set_day(not is_day)
		get_viewport().set_input_as_handled()


# ---------------- 操作(room_setup.gd から呼ばれる) ----------------
func action_for(lower: String) -> String:
	if lower.begins_with("door_leaf") or lower.begins_with("ms_doorknob"):
		return "door"
	if lower.begins_with("ph_alarmclock"):
		return "time"
	return ""


func handles(key: String) -> bool:
	return key in ["door", "time"]


func action_label(key: String) -> String:
	match key:
		"door":
			return "ドアを閉める" if door_open else "ドアを開ける"
		"time":
			return "夜にする" if is_day else "昼にする"
	return ""


func do_action(key: String) -> void:
	match key:
		"door":
			set_door(not door_open)
		"time":
			set_day(not is_day)


# ---------------- ドア ----------------
func set_door(open: bool) -> void:
	if _door == null:
		return
	door_open = open
	var tw := create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(_door, "rotation:y", _door_open_y if open else 0.0, 1.1)


# ---------------- 昼と夜 ----------------
func set_day(on: bool, instant := false) -> void:
	is_day = on
	sky_mat.panorama = _day_tex if on else _night.tex
	env.sky_rotation = Vector3(0, DAY_ROT if on else _night.rot, 0)
	sun.visible = on
	refresh_light(0.0 if instant else 1.5)
	var life: Node = main.get_node_or_null("Life")
	if life and not instant:
		life._toast("昼になりました" if on else "夜になりました")


## 窓から入る光を、昼夜・カーテン・雨からまとめて決める
func refresh_light(dur := 1.5) -> void:
	var life: Node = main.get_node_or_null("Life")
	var rain: bool = life != null and life.raining
	var curtain := 0.08 if main.curtains_closed else 1.0
	var moon: Light3D = main.get_node("Moon")
	var win: Light3D = main.get_node("WindowSky")
	var t := {}
	if is_day:
		t = {"sky": DAY_SKY_ENERGY * (0.6 if rain else 1.0), "sun": SUN_ENERGY * curtain * (0.12 if rain else 1.0), "moon": 0.0,
			"win": WIN_DAY.energy * curtain * (0.6 if rain else 1.0), "win_color": WIN_DAY.color,
			"amb_color": AMB_DAY.color, "amb": AMB_DAY.energy * (0.5 + 0.5 * curtain), "exposure": EXPOSURE_DAY, "fog": FOG_DAY}
	else:
		t = {"sky": _night.sky * (0.55 if rain else 1.0), "sun": 0.0, "moon": _night.moon * curtain * (0.25 if rain else 1.0),
			"win": _night.win * curtain, "win_color": _night.win_color,
			"amb_color": _night.amb_color, "amb": _night.amb, "exposure": _night.exposure, "fog": _night.fog}
	if dur <= 0.0:
		sky_mat.energy_multiplier = t.sky
		sun.light_energy = t.sun
		moon.light_energy = t.moon
		win.light_energy = t.win
		win.light_color = t.win_color
		env.ambient_light_color = t.amb_color
		env.ambient_light_energy = t.amb
		env.tonemap_exposure = t.exposure
		env.volumetric_fog_density = t.fog
		return
	var tw := create_tween().set_parallel(true)
	tw.tween_property(sky_mat, "energy_multiplier", t.sky, dur)
	tw.tween_property(sun, "light_energy", t.sun, dur)
	tw.tween_property(moon, "light_energy", t.moon, dur)
	tw.tween_property(win, "light_energy", t.win, dur)
	tw.tween_property(win, "light_color", t.win_color, dur)
	tw.tween_property(env, "ambient_light_color", t.amb_color, dur)
	tw.tween_property(env, "ambient_light_energy", t.amb, dur)
	tw.tween_property(env, "tonemap_exposure", t.exposure, dur)
	tw.tween_property(env, "volumetric_fog_density", t.fog, dur)


# ---------------- 廊下の照明 ----------------
func _setup_hall_lights() -> void:
	for i in 6:
		var panel = main._find("Hall_Light_%d" % i)
		if panel == null:
			continue
		var l := OmniLight3D.new()
		l.light_color = Color(0.95, 0.97, 1.0)
		l.light_energy = 1.1
		l.omni_range = 4.2
		l.omni_attenuation = 1.3
		l.light_volumetric_fog_energy = 0.15
		l.shadow_enabled = i == 2  # 自室のドアの前だけ影を落とす(負荷を抑える)
		main.add_child(l)
		l.global_position = (panel as Node3D).global_position + Vector3(0, -0.2, 0)
	var sign = main._find("Hall_Exit_Sign")
	if sign:
		var e := OmniLight3D.new()
		e.light_color = Color(1.0, 0.25, 0.2)
		e.light_energy = 0.4
		e.omni_range = 1.4
		main.add_child(e)
		e.global_position = (sign as Node3D).global_position + Vector3(0.25, -0.1, 0)
