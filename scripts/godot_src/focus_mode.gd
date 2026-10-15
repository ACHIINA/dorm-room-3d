extends Node
## 集中モード(ポモドーロタイマー)。
## F で開始・終了、Space で一時停止、↑↓ で集中の長さ、M で小窓。
## 机に座り、部屋のモニターと画面の右上に残り時間を出す。区切りでチャイムと macOS の通知。
## 記録と設定は user://focus_log.json / user://focus_settings.json に保存する。

enum Phase { IDLE, FOCUS, BREAK, LONG_BREAK }

const LOG_PATH := "user://focus_log.json"
const SET_PATH := "user://focus_settings.json"
const CYCLES := 4            # この回数の集中ごとに長い休憩
const MIN_RECORD_SEC := 60   # 途中で終えた集中も、これ以上なら記録する
const ACCENT := Color(0.89, 0.63, 0.38)
const INK := Color(0.95, 0.91, 0.84)
const SUB := Color(0.95, 0.91, 0.84, 0.62)

var settings := {"focus_min": 25, "break_min": 5, "long_break_min": 15, "autoplay": true}
var phase := Phase.IDLE
var paused := false
var cycle := 1
var phase_total := 1.0
var _end_ms := 0
var _left_when_paused := 0.0
var _focus_start_unix := 0.0
var mini := false
var _win := {}
var _log := {"days": {}}

@onready var main: Node = get_parent()
var player: CharacterBody3D
var chime: AudioStreamPlayer
var _screen: MeshInstance3D
var _screen_prev: Material
var _screen_mat: StandardMaterial3D

# 画面の右上
var panel: PanelContainer
var l_phase: Label
var l_time: Label
var bar: ProgressBar
var l_today: Label
var l_keys: Label
# 部屋のモニター
var vp: SubViewport
var m_phase: Label
var m_time: Label
var m_bar: ProgressBar
var m_today: Label


func _ready() -> void:
	player = main.get_node("Player")
	_load()
	chime = AudioStreamPlayer.new()
	chime.stream = load("res://assets/sounds/chime.wav")
	chime.volume_db = -3.0
	add_child(chime)
	_build_hud()
	_build_monitor()
	_refresh()


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var handled := true
	match event.physical_keycode:
		KEY_F:
			if phase == Phase.IDLE:
				start()
			else:
				stop()
		KEY_M:
			set_mini(not mini)
		KEY_SPACE:
			if phase == Phase.IDLE:
				handled = false
			else:
				toggle_pause()
		KEY_UP, KEY_DOWN:
			if phase == Phase.IDLE:
				handled = false
			else:
				var step := 5 if event.physical_keycode == KEY_UP else -5
				settings.focus_min = clampi(settings.focus_min + step, 5, 90)
				_save_settings()
				_refresh()
		_:
			handled = false
	if handled:
		get_viewport().set_input_as_handled()


func _process(_delta: float) -> void:
	if phase == Phase.IDLE:
		return
	if not paused and _left() <= 0.0:
		_next_phase()
	_refresh()


# ---------------- 開始・終了・一時停止 ----------------
func start() -> void:
	cycle = 1
	_begin(Phase.FOCUS)
	# 机に座り、ランプとモニターをつけ、レコードをかける
	if player._pose_key != "chair_":
		if player._pose_key != "":
			player._pose_key = ""
		player._take_pose("chair_")
	player.locked = true
	if not main.desk_lamp_on:
		main._set_desk_lamp(true)
	if not main.monitor_on:
		main._set_monitor(true)
	if settings.autoplay and not main.playing:
		main._play()
	_show_on_monitor(true)
	main.get_node("HUD/Help").visible = false


func stop() -> void:
	if phase == Phase.FOCUS:
		var done := phase_total - _left()
		if done >= MIN_RECORD_SEC:
			_record(int(round(done / 60.0)), false)
	phase = Phase.IDLE
	paused = false
	player.locked = false
	_show_on_monitor(false)
	panel.visible = false
	main.get_node("HUD/Help").visible = true
	if mini:
		set_mini(false)
	_refresh()


func toggle_pause() -> void:
	if paused:
		_end_ms = Time.get_ticks_msec() + int(_left_when_paused * 1000.0)
		paused = false
	else:
		_left_when_paused = _left()
		paused = true
	_refresh()


func _begin(p: int) -> void:
	phase = p
	paused = false
	var minutes: int = {Phase.FOCUS: settings.focus_min, Phase.BREAK: settings.break_min, Phase.LONG_BREAK: settings.long_break_min}[p]
	phase_total = minutes * 60.0
	_end_ms = Time.get_ticks_msec() + int(phase_total * 1000.0)
	if p == Phase.FOCUS:
		_focus_start_unix = Time.get_unix_time_from_system()


func _left() -> float:
	if paused:
		return _left_when_paused
	return max(0.0, (_end_ms - Time.get_ticks_msec()) / 1000.0)


func _next_phase() -> void:
	chime.play()
	if phase == Phase.FOCUS:
		var focus_min := int(round(phase_total / 60.0))
		_record(focus_min, true)
		var long := cycle % CYCLES == 0
		_begin(Phase.LONG_BREAK if long else Phase.BREAK)
		_notify("集中 %d 分が終わりました。%s %d 分" % [focus_min, "長い休憩" if long else "休憩", int(phase_total / 60.0)])
	else:
		cycle = 1 if phase == Phase.LONG_BREAK else cycle + 1
		_begin(Phase.FOCUS)
		_notify("休憩が終わりました。集中 %d 分を始めます" % settings.focus_min)


# ---------------- 通知・記録・設定 ----------------
func _notify(msg: String) -> void:
	if OS.get_name() == "macOS":
		OS.create_process("osascript", ["-e", 'display notification "%s" with title "集中モード"' % msg])


func _today() -> String:
	return Time.get_date_string_from_system()


func _record(minutes: int, completed: bool) -> void:
	var d: Dictionary = _log.days.get(_today(), {"minutes": 0, "count": 0, "sessions": []})
	d.minutes += minutes
	if completed:
		d.count += 1
	d.sessions.append({"start": Time.get_datetime_string_from_unix_time(int(_focus_start_unix + Time.get_time_zone_from_system().bias * 60)),
		"minutes": minutes, "completed": completed})
	_log.days[_today()] = d
	var f := FileAccess.open(LOG_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(_log, "  "))


func _save_settings() -> void:
	var f := FileAccess.open(SET_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(settings, "  "))


func _load() -> void:
	for pair in [[LOG_PATH, "_log"], [SET_PATH, "settings"]]:
		if FileAccess.file_exists(pair[0]):
			var data = JSON.parse_string(FileAccess.get_file_as_string(pair[0]))
			if data is Dictionary:
				if pair[1] == "_log" and data.has("days"):
					_log = data
				elif pair[1] == "settings":
					for k in data:
						settings[k] = int(data[k]) if typeof(settings.get(k)) == TYPE_INT else data[k]


func today_text() -> String:
	var d: Dictionary = _log.days.get(_today(), {"minutes": 0, "count": 0})
	var m := int(d.minutes)
	var span := ("%d時間%d分" % [m / 60, m % 60]) if m >= 60 else ("%d分" % m)
	return "今日の集中 %s（%d回）" % [span, int(d.count)]


# ---------------- 表示 ----------------
func _phase_text() -> String:
	if paused:
		return "一時停止中"
	match phase:
		Phase.FOCUS:
			return "集中 %d/%d" % [cycle, CYCLES]
		Phase.BREAK:
			return "休憩"
		Phase.LONG_BREAK:
			return "長い休憩"
	return ""


func _time_text() -> String:
	var s := int(ceil(_left()))
	return "%02d:%02d" % [s / 60, s % 60]


func _refresh() -> void:
	if not panel:
		return
	var pt := _phase_text()
	var tt := _time_text()
	var ratio := 1.0 - _left() / phase_total if phase != Phase.IDLE else 0.0
	var next := "次の集中 %d 分" % settings.focus_min
	l_phase.text = pt
	l_time.text = tt
	bar.value = ratio
	l_today.text = today_text() + "\n" + next
	l_keys.visible = not mini
	l_today.visible = not mini
	# 部屋のモニターが見えているときは右上の表示を出さない(同じ内容が二重になるため)
	panel.visible = phase != Phase.IDLE and not _monitor_in_view()
	m_phase.text = pt
	m_time.text = tt
	m_bar.value = ratio
	m_today.text = today_text()
	var col := ACCENT if phase == Phase.FOCUS and not paused else Color(0.62, 0.78, 0.86)
	l_phase.add_theme_color_override("font_color", col)
	m_phase.add_theme_color_override("font_color", col)
	_bar_color(bar, col)
	_bar_color(m_bar, col)


func _monitor_in_view() -> bool:
	if not (_screen is Node3D):
		return false
	var cam: Camera3D = player.camera
	var p: Vector3 = _screen.global_position
	if not cam.is_position_in_frustum(p) or cam.global_position.distance_to(p) > 2.5:
		return false
	# 画面の正面側から見ているか(モニターの画面は +X 向き)
	var facing: Vector3 = _screen.global_basis.x.normalized()
	return facing.dot((cam.global_position - p).normalized()) > 0.3


func _bar_color(b: ProgressBar, c: Color) -> void:
	var fill := StyleBoxFlat.new()
	fill.bg_color = c
	fill.set_corner_radius_all(3)
	b.add_theme_stylebox_override("fill", fill)


func _mono() -> SystemFont:
	var f := SystemFont.new()
	f.font_names = PackedStringArray(["SF Mono", "Menlo", "Monaco"])
	f.font_weight = 300
	return f


func _label(parent: Node, size: int, color: Color, mono := false) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if mono:
		l.add_theme_font_override("font", _mono())
	parent.add_child(l)
	return l


func _bar(parent: Node, h: int) -> ProgressBar:
	var b := ProgressBar.new()
	b.max_value = 1.0
	b.show_percentage = false
	b.custom_minimum_size = Vector2(0, h)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(1, 1, 1, 0.12)
	bg.set_corner_radius_all(3)
	b.add_theme_stylebox_override("background", bg)
	parent.add_child(b)
	return b


func _build_hud() -> void:
	var layer: CanvasLayer = main.get_node("HUD")
	panel = PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.06, 0.05, 0.72)
	sb.set_corner_radius_all(10)
	sb.content_margin_left = 22
	sb.content_margin_right = 22
	sb.content_margin_top = 14
	sb.content_margin_bottom = 16
	panel.add_theme_stylebox_override("panel", sb)
	panel.anchor_left = 1.0
	panel.anchor_right = 1.0
	panel.offset_left = -330
	panel.offset_right = -20
	panel.offset_top = 20
	panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	layer.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	panel.add_child(v)
	l_phase = _label(v, 18, ACCENT)
	l_time = _label(v, 64, INK, true)
	bar = _bar(v, 6)
	l_today = _label(v, 16, SUB)
	l_keys = _label(v, 14, Color(INK, 0.55))
	l_keys.text = "F: 終える / Space: 一時停止 / ↑↓: 集中の長さ / M: 小窓"
	panel.visible = false


func _build_monitor() -> void:
	vp = SubViewport.new()
	vp.size = Vector2i(1280, 720)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.transparent_bg = false
	add_child(vp)
	var bg := ColorRect.new()
	bg.color = Color(0.055, 0.058, 0.066)
	bg.size = Vector2(1280, 720)
	vp.add_child(bg)
	var v := VBoxContainer.new()
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.size = Vector2(1280, 720)
	v.add_theme_constant_override("separation", 18)
	vp.add_child(v)
	m_phase = _label(v, 44, ACCENT)
	m_time = _label(v, 240, INK, true)
	var bw := MarginContainer.new()
	bw.add_theme_constant_override("margin_left", 260)
	bw.add_theme_constant_override("margin_right", 260)
	v.add_child(bw)
	m_bar = _bar(bw, 10)
	m_today = _label(v, 34, SUB)
	for l in [m_phase, m_time, m_today]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_screen = main._find("DP_Mon_Screen")
	_screen_mat = StandardMaterial3D.new()
	_screen_mat.albedo_texture = vp.get_texture()
	_screen_mat.emission_enabled = true
	_screen_mat.emission_texture = vp.get_texture()
	_screen_mat.emission_energy_multiplier = 1.1
	_screen_mat.roughness = 0.18


func _show_on_monitor(on: bool) -> void:
	if not (_screen is MeshInstance3D):
		return
	if on:
		_screen_prev = _screen.get_surface_override_material(0)
		_screen.set_surface_override_material(0, _screen_mat)
	else:
		_screen.set_surface_override_material(0, _screen_prev)


# ---------------- 小窓 ----------------
func set_mini(on: bool) -> void:
	if on == mini:
		return
	mini = on
	var id := DisplayServer.MAIN_WINDOW_ID
	if on:
		_win = {"size": DisplayServer.window_get_size(id), "pos": DisplayServer.window_get_position(id), "mode": DisplayServer.window_get_mode(id)}
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED, id)
		var r := DisplayServer.screen_get_usable_rect(DisplayServer.window_get_current_screen(id))
		var sz := Vector2i(int(r.size.x * 0.3), int(r.size.x * 0.3 * 2.0 / 3.0))
		DisplayServer.window_set_size(sz, id)
		DisplayServer.window_set_position(r.position + r.size - sz - Vector2i(16, 16), id)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true, id)
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		player.allow_capture = false
	else:
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, false, id)
		DisplayServer.window_set_mode(_win.get("mode", DisplayServer.WINDOW_MODE_WINDOWED), id)
		DisplayServer.window_set_size(_win.get("size", Vector2i(1536, 1024)), id)
		DisplayServer.window_set_position(_win.get("pos", Vector2i(80, 80)), id)
		player.allow_capture = true
	_refresh()
