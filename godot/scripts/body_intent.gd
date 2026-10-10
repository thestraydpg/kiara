extends Node

## Autoload singleton ("BodyIntent" - see project.godot [autoload]).
##
## The single shared "what should the body do right now" state.
## GamepadController and TouchInteraction both write into this;
## LocomotionController, AutonomyDriver, and TeleopRecorder all read from
## it. One shared intent object means the character never has two input
## sources fighting over the same motion in the same frame - whichever
## source wrote most recently wins, and AutonomyDriver only writes once
## both have been silent past IDLE_TIMEOUT.

signal gesture_requested(name: String)

var move: Vector2 = Vector2.ZERO       # desired move, x=strafe, y=forward, camera-relative
var look: Vector2 = Vector2.ZERO       # camera yaw/pitch delta this frame, -1..1
var sprint: bool = false
var jump: bool = false
var crouch: bool = false

var last_gamepad_input_time: float = -1000.0
var last_touch_input_time: float = -1000.0
const IDLE_TIMEOUT := 2.5

func is_player_driving() -> bool:
	var t := Time.get_ticks_msec() / 1000.0
	return (t - last_gamepad_input_time) < IDLE_TIMEOUT or (t - last_touch_input_time) < IDLE_TIMEOUT

func mark_gamepad_active() -> void:
	last_gamepad_input_time = Time.get_ticks_msec() / 1000.0

func mark_touch_active() -> void:
	last_touch_input_time = Time.get_ticks_msec() / 1000.0

func request_gesture(gesture_name: String) -> void:
	gesture_requested.emit(gesture_name)
