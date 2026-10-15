extends Node3D
## 部屋の当たり判定と、ランプ・モニター・レコード・カーテンの操作。暮らしの操作は life.gd に任せる。
## プレイヤーは action_for() で視線の先の操作を調べ、do_action() で実行する。

## 布物や細かい物は当たり判定を省く(起動時の処理を軽くする)
const SKIP := ["leaf", "leaves", "bark", "vine", "stem", "fringe", "pin_", "pinned", "keys", "record", "pen", "backdrop",
		"glass", "duvet", "throw", "pillow", "blanket", "rd_cable", "sweatshirt", "pachira", "calathea", "fish_", "coffee",
		"ceiling_lamp_cord",
		"stationery", "notepads", "spectacles", "postcard"]
const MUSIC_DIR := "res://music"   # ここに mp3 / ogg / wav を入れる(.gdignore で取り込み対象外)
const RPM := 33.333 / 60.0 * TAU   # レコードの回転(ラジアン/秒)
const ARM_REST := deg_to_rad(25.0) # トーンアームを外した角度
const CURTAIN_OPEN := 0.2          # 開いたときの幅の比率

var desk_lamp_on := true
var globe_on := true
var monitor_on := true
var curtains_closed := false
var playing := false
var tracks: Array[String] = []
var life: Node
var world: Node
var dorm: Node
var track_index := 0

@onready var room: Node3D = $Room
@onready var audio: AudioStreamPlayer3D = $RecordPlayer

var _spin: Array[Node3D] = []
var _arm_pivot: Node3D
var _curtains: Array[Node3D] = []
var _base := {}


func _ready() -> void:
	_add_collisions(room)
	for n in ["Shelf_TT_Platter", "Shelf_TT_Record", "Shelf_TT_Label"]:
		var s := _find(n)
		if s:
			_spin.append(s)
	_setup_tonearm()
	for n in ["Curtain_L", "Curtain_R"]:
		var c := _find(n)
		if c:
			c.scale.x = CURTAIN_OPEN
			_curtains.append(c)
	# 点け消しする発光体と動くカーテンは SDFGI(光の跳ね返り)に焼き込まない。
	# SDFGI は発光を最初に一度だけ記録するので、消しても光が残ってしまうため
	for n in ["DP_Lamp_Bulb", "Shelf_GlobeLamp", "DP_Mon_Screen", "Curtain_L", "Curtain_R"]:
		var gi := _find(n)
		if gi is GeometryInstance3D:
			gi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	for n in ["WarmBounce", "WindowSky", "Moon"]:
		_base[n] = get_node(n).light_energy
	if _spin.size() > 0:
		audio.global_position = _spin[0].global_position + Vector3(0, 0.1, 0)
	audio.finished.connect(_on_track_finished)
	tracks = _scan_music()
	var focus: Node = load("res://scripts/focus_mode.gd").new()
	focus.name = "FocusMode"
	add_child(focus)
	life = load("res://scripts/life.gd").new()
	life.name = "Life"
	add_child(life)
	world = load("res://scripts/world.gd").new()
	world.name = "World"
	add_child(world)
	dorm = load("res://scripts/dorm.gd").new()
	dorm.name = "Dorm"
	add_child(dorm)
	var visuals: Node = load("res://scripts/visuals.gd").new()
	visuals.name = "Visuals"
	add_child(visuals)   # 見た目の仕上げは最後(ほかが作ったライトにも効かせる)


func _process(delta: float) -> void:
	if playing:
		for s in _spin:
			s.rotate_y(-RPM * delta)


# ---------------- プレイヤーから呼ばれる ----------------
func action_for(lower_name: String) -> String:
	if world:
		var wk: String = world.action_for(lower_name)
		if wk != "":
			return wk
	if dorm:
		var dk: String = dorm.action_for(lower_name)
		if dk != "":
			return dk
	if life:
		var k: String = life.action_for(lower_name)
		if k != "":
			return k
	if lower_name.begins_with("dp_lamp"):
		return "desk_lamp"
	if lower_name.begins_with("shelf_globelamp"):
		return "globe_lamp"
	if lower_name.begins_with("dp_mon"):
		return "monitor"
	if lower_name.begins_with("shelf_tt"):
		return "turntable"
	if lower_name.begins_with("curtain"):
		return "curtain"
	return ""


func action_label(key: String) -> String:
	if world and world.handles(key):
		return world.action_label(key)
	if dorm and dorm.handles(key):
		return dorm.action_label(key)
	if life and life.handles(key):
		return life.action_label(key)
	match key:
		"desk_lamp":
			return "デスクランプを消す" if desk_lamp_on else "デスクランプをつける"
		"globe_lamp":
			return "ランプを消す" if globe_on else "ランプをつける"
		"monitor":
			return "モニターを消す" if monitor_on else "モニターをつける"
		"turntable":
			if tracks.is_empty():
				return "レコードをかける(music フォルダに曲がありません)"
			var name := tracks[track_index].get_file().get_basename()
			return ("レコードを止める / R: 次の曲  ♪ " + name) if playing else ("レコードをかける  ♪ " + name)
		"curtain":
			return "カーテンを開ける" if curtains_closed else "カーテンを閉める"
	return ""


func do_action(key: String) -> void:
	if world and world.handles(key):
		world.do_action(key)
		return
	if dorm and dorm.handles(key):
		dorm.do_action(key)
		return
	if life and life.handles(key):
		life.do_action(key)
		return
	match key:
		"desk_lamp":
			_set_desk_lamp(not desk_lamp_on)
		"globe_lamp":
			_set_globe(not globe_on)
		"monitor":
			_set_monitor(not monitor_on)
		"turntable":
			if playing:
				_stop()
			else:
				_play()
		"curtain":
			_set_curtains(not curtains_closed)


func next_track() -> void:
	if tracks.is_empty():
		return
	track_index = (track_index + 1) % tracks.size()
	if playing:
		_play()


# ---------------- ランプ ----------------
func _set_desk_lamp(on: bool) -> void:
	desk_lamp_on = on
	$DeskLamp.visible = on
	$DeskLampGlow.visible = on
	_set_emission(_find("DP_Lamp_Bulb"), on)
	_update_bounce()


func _set_globe(on: bool) -> void:
	globe_on = on
	$GlobeLamp.visible = on
	_set_emission(_find("Shelf_GlobeLamp"), on)
	_update_bounce()


func _set_monitor(on: bool) -> void:
	monitor_on = on
	$MonitorLight.visible = on
	var mi := _find("DP_Mon_Screen")
	_set_emission(mi, on)
	# 消したときは壁紙ではなく黒い画面にする
	var m: Material = mi.get_surface_override_material(0) if mi else null
	if m is StandardMaterial3D:
		if not m.has_meta("albedo_tex"):
			m.set_meta("albedo_tex", m.albedo_texture)
		m.albedo_texture = m.get_meta("albedo_tex") if on else null
		m.albedo_color = Color.WHITE if on else Color(0.015, 0.015, 0.015)


func _update_bounce() -> void:
	# 部屋全体の暖かい照り返しはランプの数に合わせて弱める
	var k := 0.15 + 0.6 * float(desk_lamp_on) + 0.25 * float(globe_on)
	create_tween().tween_property($WarmBounce, "light_energy", _base["WarmBounce"] * k, 0.3)


func _set_emission(mi: Node, on: bool) -> void:
	if not (mi is MeshInstance3D):
		return
	var m: Material = mi.get_surface_override_material(0)
	if m == null:
		m = mi.get_active_material(0).duplicate()
		mi.set_surface_override_material(0, m)
	if m is StandardMaterial3D:
		m.emission_enabled = on


# ---------------- レコード ----------------
func _scan_music() -> Array[String]:
	var out: Array[String] = []
	var dir := ProjectSettings.globalize_path(MUSIC_DIR)
	var d := DirAccess.open(dir)
	if d == null:
		return out
	for f in d.get_files():
		if f.get_extension().to_lower() in ["mp3", "ogg", "wav"]:
			out.append(dir.path_join(f))
	out.sort()
	return out


func _load_stream(path: String) -> AudioStream:
	match path.get_extension().to_lower():
		"mp3":
			return AudioStreamMP3.load_from_file(path)
		"ogg":
			return AudioStreamOggVorbis.load_from_file(path)
		"wav":
			return AudioStreamWAV.load_from_file(path)
	return null


func _play() -> void:
	if tracks.is_empty():
		return
	var s := _load_stream(tracks[track_index])
	if s == null:
		push_warning("読み込めない曲: " + tracks[track_index])
		return
	if "loop" in s:
		s.loop = false
	audio.stream = s
	audio.play()
	playing = true
	_move_arm(true)


func _stop() -> void:
	playing = false
	audio.stop()
	_move_arm(false)


func _on_track_finished() -> void:
	if playing:
		if life:
			life.on_track_finished()
		next_track()


func _setup_tonearm() -> void:
	var base := _find("Shelf_TT_ArmBase")
	if base == null:
		return
	_arm_pivot = Node3D.new()
	_arm_pivot.name = "TonearmPivot"
	base.get_parent().add_child(_arm_pivot)
	_arm_pivot.global_position = base.global_position
	for n in ["Shelf_TT_Arm", "Shelf_TT_Head"]:
		var p := _find(n)
		if p:
			p.reparent(_arm_pivot, true)
	_arm_pivot.rotation.y = ARM_REST


func _move_arm(on_record: bool) -> void:
	if _arm_pivot:
		create_tween().set_trans(Tween.TRANS_SINE).tween_property(_arm_pivot, "rotation:y", 0.0 if on_record else ARM_REST, 1.2)


# ---------------- カーテン ----------------
func _set_curtains(closed: bool) -> void:
	curtains_closed = closed
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	for c in _curtains:
		tw.tween_property(c, "scale:x", 1.0 if closed else CURTAIN_OPEN, 1.6)
	# 閉めると窓からの光(昼は太陽、夜は月)が入らなくなる。明るさは World でまとめて計算する
	if world:
		world.refresh_light(1.6)


# ---------------- 共通 ----------------
func _find(n: String) -> Node:
	var hit := room.find_child(n, true, false)
	return hit if hit else room.find_child(n + "_*", true, false)


func _add_collisions(node: Node) -> void:
	for child in node.get_children():
		if child is MeshInstance3D:
			var lower := String(child.name).to_lower()
			var skip := false
			for word in SKIP:
				if lower.begins_with("door_leaf"):
					break  # ドアの板(Door_Leaf)は "leaf" を含むが当たり判定が必要
				if lower.contains(word):
					skip = true
					break
			if not skip:
				child.create_trimesh_collision()
				# ランプのシェードのような片面メッシュも外側から当たるように
				for body in child.get_children():
					if body is StaticBody3D:
						for cs in body.get_children():
							if cs is CollisionShape3D and cs.shape is ConcavePolygonShape3D:
								cs.shape.backface_collision = true
		_add_collisions(child)
