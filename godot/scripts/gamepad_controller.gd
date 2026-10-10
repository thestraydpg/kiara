extends Node
class_name GamepadController

## GTA-style on-foot Xbox control scheme (Rockstar on-foot convention,
## adapted for an unarmed character), polled directly from the first
## connected joypad rather than through InputMap actions, so it works
## standalone without the project's input bindings being set up.
##
##   Left stick    - move (walk; push past ~0.85 magnitude to run)
##   Right stick   - camera orbit (yaw/pitch)
##   A             - jump
##   X (hold)      - sprint
##   B             - crouch / cover toggle
##   Y             - wave gesture (routed through MCUBridge/BodyIntent;
##                   no-op if nothing is listening yet)
##   RT            - grab / interact with right hand
##   LT            - grab / interact with left hand
##
## Writes into the BodyIntent autoload singleton - this script owns no
## bones or movement itself, same ownership-separation pattern as every
## other piece of the rig (MCUBridge, SpringBoneRig).

@export var device: int = 0
const DEADZONE := 0.18

var _y_was_pressed: bool = false

func _process(_delta: float) -> void:
	if not Input.is_joy_known(device):
		return

	var move := Vector2(
		Input.get_joy_axis(device, JOY_AXIS_LEFT_X),
		Input.get_joy_axis(device, JOY_AXIS_LEFT_Y)
	)
	var look := Vector2(
		Input.get_joy_axis(device, JOY_AXIS_RIGHT_X),
		Input.get_joy_axis(device, JOY_AXIS_RIGHT_Y)
	)

	var jump := Input.is_joy_button_pressed(device, JOY_BUTTON_A)
	var sprint := Input.is_joy_button_pressed(device, JOY_BUTTON_X)
	var crouch := Input.is_joy_button_pressed(device, JOY_BUTTON_B)
	var wave := Input.is_joy_button_pressed(device, JOY_BUTTON_Y)
	var grab_r := Input.get_joy_axis(device, JOY_AXIS_TRIGGER_RIGHT) > 0.3
	var grab_l := Input.get_joy_axis(device, JOY_AXIS_TRIGGER_LEFT) > 0.3

	var active := (move.length() > DEADZONE or look.length() > DEADZONE
		or jump or sprint or crouch or wave or grab_r or grab_l)

	BodyIntent.move = move if move.length() > DEADZONE else Vector2.ZERO
	BodyIntent.look = look if look.length() > DEADZONE else Vector2.ZERO
	BodyIntent.jump = jump
	BodyIntent.sprint = sprint
	BodyIntent.crouch = crouch

	if active:
		BodyIntent.mark_gamepad_active()

	# edge-trigger the gesture so holding Y doesn't spam requests every frame
	if wave and not _y_was_pressed:
		BodyIntent.request_gesture("wave")
	_y_was_pressed = wave
