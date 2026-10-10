extends CharacterBody3D
class_name LocomotionController

## Owns root motion only (position + facing) - the same ownership
## boundary MCUBridge documents for itself (expressive bones) and
## SpringBoneRig documents for itself (jiggle bones): this script never
## touches arm/head/spine bones, so all three compose without fighting
## over the same joint in the same frame.
##
## Drives from the BodyIntent autoload, written to by GamepadController
## and TouchInteraction. When neither has written recently
## (BodyIntent.is_player_driving() is false), AutonomyDriver takes over
## and writes its own intent instead - this script doesn't know or care
## which source is actually driving it.
##
## Also owns whole-body grab/drag/place from TouchInteraction: while
## "held" (mouse/touch grabbed), physics movement is suspended and
## position/yaw are driven directly from drag deltas instead.
##
## has_skin / receive_caress() duck-type the same tiny interface any
## other Straygents character's root controller should expose for
## TouchInteraction's pet/caress gesture to find - robots in the wider
## roster set has_skin = false and simply never receive caress.

@export var visual_path: NodePath       # Node3D that actually faces the move direction
@export var camera_rig_path: NodePath   # ThirdPersonCamera, reads BodyIntent.look itself
@export var touch_path: NodePath        # TouchInteraction, for grab/drag/place signals
@export var walk_speed: float = 1.4
@export var run_speed: float = 3.2
@export var sprint_speed: float = 5.0
@export var jump_velocity: float = 4.5
@export var turn_speed: float = 6.0
const GRAVITY := 9.8

@export var has_skin: bool = true
signal caress_received(point: Vector3, normal: Vector3, speed: float)

var _visual: Node3D
var _held: bool = false

func _ready() -> void:
	if visual_path != NodePath():
		_visual = get_node(visual_path)
	if touch_path != NodePath():
		var touch := get_node(touch_path)
		touch.body_grabbed.connect(_on_body_grabbed)
		touch.body_dragged.connect(_on_body_dragged)
		touch.body_placed.connect(_on_body_placed)
		touch.caressed.connect(_on_caressed)

func _physics_process(delta: float) -> void:
	if _held:
		velocity = Vector3.ZERO
		return

	var move: Vector2 = BodyIntent.move
	var speed := walk_speed
	if move.length() > 0.85:
		speed = run_speed
	if BodyIntent.sprint:
		speed = sprint_speed

	# move.x/y are already camera-relative (ThirdPersonCamera's facing),
	# interpreted here directly in this node's local XZ plane.
	var cam_yaw := 0.0
	if camera_rig_path != NodePath():
		cam_yaw = (get_node(camera_rig_path) as Node3D).rotation.y
	var dir := Vector3(move.x, 0, move.y).rotated(Vector3.UP, cam_yaw)
	dir.y = 0

	if dir.length() > 0.001:
		dir = dir.normalized()
		if _visual:
			var target_yaw := atan2(dir.x, dir.z)
			_visual.rotation.y = lerp_angle(_visual.rotation.y, target_yaw, clamp(turn_speed * delta, 0.0, 1.0))

	velocity.x = dir.x * speed
	velocity.z = dir.z * speed

	if is_on_floor():
		if BodyIntent.jump:
			velocity.y = jump_velocity
	else:
		velocity.y -= GRAVITY * delta

	move_and_slide()

func _on_body_grabbed(_point: Vector3) -> void:
	_held = true

func _on_body_dragged(world_delta: Vector3, yaw_delta: float) -> void:
	if not _held:
		return
	global_position += world_delta
	if _visual:
		_visual.rotation.y += yaw_delta

func _on_body_placed(point: Vector3, _normal: Vector3) -> void:
	_held = false
	global_position = point + Vector3.UP * 0.02

func _on_caressed(point: Vector3, normal: Vector3, speed: float) -> void:
	if has_skin:
		caress_received.emit(point, normal, speed)
