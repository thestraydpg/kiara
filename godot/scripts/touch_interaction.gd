extends Node
class_name TouchInteraction

## Mouse (desktop) and touchscreen (mobile) manipulation of the whole
## character, plus a separate lightweight "caress" gesture for anything
## with skin.
##
## Gestures:
##   single click/touch + drag (NOT preceded by a double-tap)
##       on a has_skin target  -> caressed signal, with the stroke's
##       measured speed. Robots in the wider Straygents roster set
##       has_skin = false on their root controller and simply never
##       receive this - grabbing below still works on them identically.
##   double-tap-and-hold        -> GRAB: body_grabbed, then every
##       subsequent drag sample while held emits body_dragged (translate
##       + yaw). Releasing emits body_placed at the release point -
##       "the second click always grabs whatever place it landed on":
##       the raycast hit at release time becomes her new anchor, not
##       wherever the drag happened to leave her floating.
##
## This node owns no bones or position directly - it only emits signals.
## LocomotionController listens for them and does the actual moving,
## same ownership-separation pattern as the rest of the rig.

signal body_grabbed(world_point: Vector3)
signal body_dragged(world_delta: Vector3, yaw_delta: float)
signal body_placed(world_point: Vector3, surface_normal: Vector3)
signal caressed(world_point: Vector3, surface_normal: Vector3, speed: float)

@export var camera_path: NodePath
@export var double_tap_window: float = 0.35
@export var caress_min_speed: float = 0.02      # below this it reads as a motionless hold, not a stroke
@export var caress_max_speed: float = 3.0       # faster than this reads as a shove, not a caress

var _camera: Camera3D

var _last_tap_time: float = -1000.0
var _tap_count: int = 0
var _press_pos: Vector2 = Vector2.ZERO
var _is_grabbing: bool = false
var _grabbed_collider: Object = null
var _last_drag_world: Vector3 = Vector3.ZERO
var _last_drag_time: float = 0.0

func _ready() -> void:
	if camera_path != NodePath():
		_camera = get_node(camera_path)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index != MOUSE_BUTTON_LEFT:
			return
		if event.pressed:
			_on_press(event.position)
		else:
			_on_release(event.position)
	elif event is InputEventScreenTouch:
		if event.pressed:
			_on_press(event.position)
		else:
			_on_release(event.position)
	elif event is InputEventScreenDrag:
		_on_drag_move(event.position)
	elif event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		_on_drag_move(event.position)

func _on_press(screen_pos: Vector2) -> void:
	var now := Time.get_ticks_msec() / 1000.0
	_tap_count = (_tap_count + 1) if (now - _last_tap_time < double_tap_window) else 1
	_last_tap_time = now
	_press_pos = screen_pos

	var hit := _raycast(screen_pos)
	if hit.is_empty():
		_grabbed_collider = null
		return
	_grabbed_collider = hit["collider"]
	_last_drag_world = hit["position"]
	_last_drag_time = now
	BodyIntent.mark_touch_active()

	if _tap_count >= 2:
		_is_grabbing = true
		body_grabbed.emit(_last_drag_world)

func _on_drag_move(screen_pos: Vector2) -> void:
	if _grabbed_collider == null:
		return
	var hit := _raycast(screen_pos)
	if hit.is_empty():
		return
	var now := Time.get_ticks_msec() / 1000.0
	var world_pos: Vector3 = hit["position"]
	var dt: float = max(now - _last_drag_time, 0.001)
	var delta: Vector3 = world_pos - _last_drag_world
	var speed: float = delta.length() / dt
	BodyIntent.mark_touch_active()

	if _is_grabbing:
		var yaw_delta := (screen_pos.x - _press_pos.x) * 0.002
		body_dragged.emit(delta, yaw_delta)
		_press_pos = screen_pos
	elif speed > caress_min_speed and speed < caress_max_speed:
		var has_skin = _grabbed_collider.get("has_skin")
		if has_skin == true:
			caressed.emit(world_pos, hit.get("normal", Vector3.UP), speed)

	_last_drag_world = world_pos
	_last_drag_time = now

func _on_release(screen_pos: Vector2) -> void:
	if _is_grabbing:
		var hit := _raycast(screen_pos)
		if not hit.is_empty():
			body_placed.emit(hit["position"], hit.get("normal", Vector3.UP))
	_is_grabbing = false
	_grabbed_collider = null

func _raycast(screen_pos: Vector2) -> Dictionary:
	if _camera == null:
		return {}
	var from := _camera.project_ray_origin(screen_pos)
	var to := from + _camera.project_ray_normal(screen_pos) * 1000.0
	var space := _camera.get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(from, to)
	return space.intersect_ray(query)
