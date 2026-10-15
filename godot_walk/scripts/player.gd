extends CharacterBody3D
## 一人称で歩くプレイヤー。
## WASD 移動 / マウス 視点 / Shift 速く歩く / Space ジャンプ
## E 座る・横になる・立ち上がる、ランプ・レコード・カーテンの操作 / R 次の曲

@export var walk_speed := 1.4
@export var fast_speed := 2.8
@export var jump_velocity := 4.0
@export var mouse_sensitivity := 0.0022
@export var reach := 2.6

const GRAVITY := 9.8
const HEAD_HEIGHT := 1.5

## 家具ごとの姿勢。名前の一部で判定する。head は頭の位置、yaw/pitch は向き(ラジアン)。
var POSES := {  # dorm.gd がラウンジのソファを追加する
	"bed_": {"label": "ベッドに横になる", "head": Vector3(0.15, 0.80, -4.05), "yaw": 1.95, "pitch": 0.02},  # 横向きに寝て机の方を見る
	"arm_": {"label": "アームチェアに座る", "head": Vector3(-1.84, 1.05, -4.17), "yaw": 2.72, "pitch": -0.10},
	"chair_": {"label": "椅子に座る", "head": Vector3(-1.62, 1.12, -2.62), "yaw": 1.33, "pitch": -0.12},
}

@onready var head: Node3D = $Head
@onready var camera: Camera3D = $Head/Camera3D
@onready var collision: CollisionShape3D = $Collision
@onready var prompt: Label = get_node_or_null("../HUD/Prompt")
@onready var room_ctl: Node = get_parent()  # room_setup.gd(ランプ・レコード・カーテン)

var _pose_key := ""          # 今の姿勢(空なら立っている)
var _stand_xf: Transform3D   # 立ち上がるときに戻る位置
var _stand_pitch := 0.0
var _moving := false
var _target_key := ""      # 姿勢のキー(POSES)
var _target_action := ""   # 部屋の操作のキー(room_setup.gd)
var locked := false        # 集中モード中は座ったまま(E で立ち上がらない)
var _bob_t := 0.0          # 歩くときの頭の揺れ
var _last_step_phase := 0.0
var _steps: Array[AudioStream] = []
var _step_player: AudioStreamPlayer
var allow_capture := true  # 小窓モードではマウスを捕まえない


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	for i in 4:
		var st = load("res://assets/sounds/step_%d.wav" % i)
		if st:
			_steps.append(st)
	_step_player = AudioStreamPlayer.new()
	_step_player.volume_db = -15.0
	add_child(_step_player)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED and not _moving:
		rotate_y(-event.relative.x * mouse_sensitivity)
		head.rotate_x(-event.relative.y * mouse_sensitivity)
		head.rotation.x = clamp(head.rotation.x, deg_to_rad(-85.0), deg_to_rad(85.0))
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		elif event.physical_keycode == KEY_E and not _moving:
			if _target_action != "":
				room_ctl.do_action(_target_action)
			elif _pose_key != "" and not locked:
				_stand_up()
			elif _target_key != "":
				_take_pose(_target_key)
		elif event.physical_keycode == KEY_R and _target_action == "turntable":
			room_ctl.next_track()
	elif event is InputEventMouseButton and event.pressed and allow_capture:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _physics_process(delta: float) -> void:
	if _pose_key != "" or _moving:
		_target_key = ""
		_target_action = _look_action()
		_update_prompt()
		return
	if not is_on_floor():
		velocity.y -= GRAVITY * delta
	elif Input.is_physical_key_pressed(KEY_SPACE):
		velocity.y = jump_velocity
	var x := float(Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_A))
	var z := float(Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_W))
	var dir := (transform.basis * Vector3(x, 0.0, z)).normalized()
	var speed := fast_speed if Input.is_physical_key_pressed(KEY_SHIFT) else walk_speed
	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	move_and_slide()
	_head_bob(delta)
	_target_key = _look_target()
	_target_action = _look_action()
	_update_prompt()


## 歩くときの頭の上下と左右の揺れ、足音
func _head_bob(delta: float) -> void:
	var hv := Vector2(velocity.x, velocity.z).length()
	if is_on_floor() and hv > 0.2:
		_bob_t += delta * hv * 1.35
		var phase := fmod(_bob_t, 1.0)
		if phase < _last_step_phase and _steps.size() > 0:  # 1 歩ごと
			_step_player.stream = _steps[randi() % _steps.size()]
			_step_player.pitch_scale = randf_range(0.92, 1.08)
			_step_player.play()
		_last_step_phase = phase
	else:
		_bob_t = lerp(_bob_t, round(_bob_t), clamp(delta * 4.0, 0.0, 1.0))
	var amp: float = clamp(hv / 2.8, 0.0, 1.0)
	head.position.y = HEAD_HEIGHT + sin(_bob_t * TAU) * 0.016 * amp
	head.position.x = sin(_bob_t * PI) * 0.012 * amp


## 視線の先の物体と、その親たちの名前(小文字)を返す
func _look_names() -> Array[String]:
	var out: Array[String] = []
	var from := camera.global_position
	var to := from - camera.global_basis.z * reach
	var q := PhysicsRayQueryParameters3D.create(from, to)
	q.exclude = [get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return out
	var n: Node = hit.collider
	while n:
		out.append(String(n.name).to_lower())
		n = n.get_parent()
	return out


## 視線の先にある家具の姿勢キー(なければ空)
func _look_target() -> String:
	for lower in _look_names():
		for key in POSES:
			if lower.begins_with(key):
				return key
	return ""


## 視線の先にある部屋の操作キー(なければ空)
func _look_action() -> String:
	if not room_ctl.has_method("action_for"):
		return ""
	for lower in _look_names():
		var key: String = room_ctl.action_for(lower)
		if key == "monitor" and locked:
			return ""  # 集中モード中はモニターにタイマーを出しているので消させない
		if key != "":
			return key
	var life: Node = room_ctl.get_node_or_null("Life")
	if life:
		return life.aim_action(camera)
	return ""


func _update_prompt() -> void:
	if not prompt:
		return
	_set_prompt_text()
	if _pose_key == "bed_" and not locked and not prompt.text.contains("Z:"):
		prompt.text += (" / " if prompt.text != "" else "") + "Z: 眠る"


func _set_prompt_text() -> void:
	if _target_action != "":
		prompt.text = "E: " + room_ctl.action_label(_target_action)
	elif _pose_key != "":
		if locked:
			prompt.text = ""
		elif _pose_key == "bed_":
			prompt.text = "E: 立ち上がる / Z: 眠る"
		else:
			prompt.text = "E: 立ち上がる"
	elif _target_key != "":
		prompt.text = "E: " + POSES[_target_key]["label"]
	else:
		prompt.text = ""


func _take_pose(key: String) -> void:
	var p: Dictionary = POSES[key]
	_stand_xf = global_transform
	_stand_pitch = head.rotation.x
	_pose_key = key
	velocity = Vector3.ZERO
	collision.disabled = true
	_move_to(p["head"] - Vector3(0, HEAD_HEIGHT, 0), p["yaw"], p["pitch"])


func _stand_up() -> void:
	_pose_key = ""
	await _move_to(_stand_xf.origin, _stand_xf.basis.get_euler().y, _stand_pitch)
	collision.disabled = false


func _move_to(pos: Vector3, yaw: float, pitch: float) -> void:
	_moving = true
	# 一番近い回り方で向きを変える
	var y0 := rotation.y
	var y1 := y0 + wrapf(yaw - y0, -PI, PI)
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(self, "global_position", pos, 0.9)
	tw.tween_property(self, "rotation:y", y1, 0.9)
	tw.tween_property(head, "rotation:x", pitch, 0.9)
	await tw.finished
	_moving = false
