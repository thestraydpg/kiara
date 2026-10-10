extends SpringArm3D
class_name ThirdPersonCamera

## GTA-style follow camera: yaw/pitch driven entirely by BodyIntent.look
## (right stick on gamepad; mouse look can feed the same field later if
## wanted), independent of the character body's own facing so strafing
## doesn't spin the camera. LocomotionController reads this node's own
## yaw back to decide which way "forward" means for movement input - the
## two scripts stay in sync without either owning the other.

@export var yaw_speed: float = 2.5
@export var pitch_speed: float = 1.8
@export var min_pitch: float = -0.6
@export var max_pitch: float = 0.5
@export var recenter_on_idle: bool = false

func _process(delta: float) -> void:
	var look: Vector2 = BodyIntent.look
	rotation.y -= look.x * yaw_speed * delta
	rotation.x = clamp(rotation.x - look.y * pitch_speed * delta, min_pitch, max_pitch)
