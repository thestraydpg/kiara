extends Node
class_name SpringBoneChain

## Runtime secondary-motion (jiggle) physics for a Skeleton3D.
##
## The Blender-side rig only supplies the skin binding (which vertices move
## with which bone) - the actual jiggle motion is a spring-damper simulation
## that must run every physics frame here, driven by how fast the PARENT
## bone (spine/pelvis/sternum) is accelerating. This is the same technique
## used for breast/belly/glute secondary motion in most 3D character
## engines (VRM SpringBone, Unity DynamicBone, etc.) since full soft-body
## simulation is too expensive to run per-frame on a whole character.
##
## Usage: attach one SpringBoneChain per jiggle bone to the character's
## Skeleton3D, or use SpringBoneRig (spring_bone_rig.gd) to set up the
## full standard set in one place.

@export var skeleton_path: NodePath
@export var bone_name: String = ""
@export var stiffness: float = 0.65       # 0..1, higher = snaps back faster, less bounce
@export var damping: float = 0.35         # 0..1, higher = settles faster, less oscillation
@export var gravity_influence: float = 0.4
@export var drag: float = 0.08            # extra air resistance, independent of damping
@export var max_swing_degrees: float = 45.0  # hard clamp so motion can't look broken

var _skeleton: Skeleton3D
var _bone_idx: int = -1
var _parent_bone_idx: int = -1
var _rest_local_pos: Vector3
var _bone_length: float = 0.1

# Simulation state lives in WORLD space - this is what makes it jiggle
# physics rather than a static sag. If it lived in the parent's local
# space, "rest" would never appear to move when the parent moves fast
# (it's defined relative to the parent), so there would be nothing for
# the spring to lag behind and no inertia/bounce would ever show up.
var _tail_world: Vector3 = Vector3.ZERO
var _velocity_world: Vector3 = Vector3.ZERO
var _initialized: bool = false

func _ready() -> void:
	_skeleton = get_node(skeleton_path) as Skeleton3D
	if _skeleton == null:
		push_error("SpringBoneChain: skeleton_path does not point to a Skeleton3D")
		return

	_bone_idx = _skeleton.find_bone(bone_name)
	if _bone_idx < 0:
		push_error("SpringBoneChain: bone '%s' not found in skeleton" % bone_name)
		return

	_parent_bone_idx = _skeleton.get_bone_parent(_bone_idx)
	_rest_local_pos = _skeleton.get_bone_rest(_bone_idx).origin
	_bone_length = _rest_local_pos.length()
	if _bone_length < 0.001:
		_bone_length = 0.05

func _parent_global_transform() -> Transform3D:
	if _parent_bone_idx >= 0:
		return _skeleton.global_transform * _skeleton.get_bone_global_pose(_parent_bone_idx)
	return _skeleton.global_transform

func _physics_process(delta: float) -> void:
	if _skeleton == null or _bone_idx < 0:
		return

	var parent_global := _parent_global_transform()
	var rest_world: Vector3 = parent_global * _rest_local_pos

	if not _initialized:
		_tail_world = rest_world
		_initialized = true

	# Spring pulls the simulated tip back toward where it "should" be;
	# since rest_world moves instantly with the parent but _tail_world has
	# momentum, a fast parent movement makes the tip lag behind and then
	# overshoot/settle - that lag+overshoot IS the jiggle.
	var spring_force: Vector3 = (rest_world - _tail_world) * stiffness
	var gravity_force: Vector3 = Vector3(0, -1, 0) * gravity_influence * _bone_length
	_velocity_world += (spring_force + gravity_force) * delta * 60.0
	_velocity_world *= clamp(1.0 - damping - drag, 0.0, 1.0)
	_tail_world += _velocity_world * delta

	# Keep bone length constant - the tip stays on a sphere of radius
	# _bone_length around the pivot (parent_global.origin), it doesn't stretch.
	var pivot := parent_global.origin
	var offset := _tail_world - pivot
	if offset.length() > 0.0001:
		_tail_world = pivot + offset.normalized() * _bone_length
	else:
		_tail_world = pivot + Vector3(0, 0, _bone_length)

	# Clamp max swing angle from rest so a hard shove can't flip the chain
	# inside out or point it through the body.
	var rest_dir := (rest_world - pivot).normalized()
	var tail_dir := (_tail_world - pivot).normalized()
	var angle := rad_to_deg(rest_dir.angle_to(tail_dir))
	if angle > max_swing_degrees and rest_dir.cross(tail_dir).length() > 0.0001:
		var axis := rest_dir.cross(tail_dir).normalized()
		tail_dir = rest_dir.rotated(axis, deg_to_rad(max_swing_degrees))
		_tail_world = pivot + tail_dir * _bone_length

	# Convert the simulated world-space tip back into a bone pose rotation:
	# rotate from the bone's rest direction to the direction toward the tip.
	var target_local: Vector3 = parent_global.affine_inverse() * _tail_world
	var rest_dir_local := _rest_local_pos.normalized()
	var target_dir_local := target_local.normalized()
	var rot_axis := rest_dir_local.cross(target_dir_local)
	var pose_basis := Basis.IDENTITY
	if rot_axis.length() > 0.0001:
		var rot_angle := rest_dir_local.angle_to(target_dir_local)
		pose_basis = Basis(rot_axis.normalized(), rot_angle)
	_skeleton.set_bone_pose_rotation(_bone_idx, pose_basis.get_rotation_quaternion())
