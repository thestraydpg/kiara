extends Node
class_name TeleopRecorder

## Logs (controller input, resulting root motion) to a JSONL file
## whenever BodyIntent.is_player_driving() is true - this is the capture
## half of "she learns her body from how I move the controller".
##
## This only ever WRITES data; no learning happens in Godot. The intended
## consumer is mujoco/teleop_to_commands.py, which turns a recorded
## session into a command trajectory (target speed/heading over time)
## that locomotion_env.py can train against instead of one fixed
## constant target_speed - so the gait the MuJoCo policy converges on is
## shaped by how a real session actually moved her, not just whatever
## PPO's reward function found on its own.
##
## Root motion only, matching LocomotionController's own ownership
## boundary - this does not (and can't, from Godot alone) capture
## individual joint torques, since the Godot-side body is a simple
## capsule controller, not the full MuJoCo biomechanical rig.

@export var out_path: String = "user://teleop_log.jsonl"
@export var sample_hz: float = 20.0
@export var body_path: NodePath

var _body: CharacterBody3D
var _file: FileAccess
var _accum: float = 0.0

func _ready() -> void:
	if body_path != NodePath():
		_body = get_node(body_path)
	_file = FileAccess.open(out_path, FileAccess.WRITE)
	if _file:
		print("TeleopRecorder: writing to ", ProjectSettings.globalize_path(out_path))

func _physics_process(delta: float) -> void:
	if _file == null or _body == null:
		return
	if not BodyIntent.is_player_driving():
		return
	_accum += delta
	var period := 1.0 / sample_hz
	if _accum < period:
		return
	_accum = 0.0

	var sample := {
		"t": Time.get_ticks_msec() / 1000.0,
		"input": {
			"move": [BodyIntent.move.x, BodyIntent.move.y],
			"look": [BodyIntent.look.x, BodyIntent.look.y],
			"sprint": BodyIntent.sprint, "jump": BodyIntent.jump, "crouch": BodyIntent.crouch,
		},
		"state": {
			"pos": [_body.global_position.x, _body.global_position.y, _body.global_position.z],
			"yaw": _body.rotation.y,
			"vel": [_body.velocity.x, _body.velocity.y, _body.velocity.z],
		},
	}
	_file.store_line(JSON.stringify(sample))

func _exit_tree() -> void:
	if _file:
		_file.flush()
