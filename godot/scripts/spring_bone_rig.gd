extends Node
class_name SpringBoneRig

## Sets up the full standard set of SpringBoneChain instances for Kiara's
## jiggle bones in one place, with per-region physics tuning, instead of
## hand-wiring each one in the editor.
##
## Attach this as a child of the character root (sibling of the Skeleton3D),
## set skeleton_path, and it builds the chains in _ready().

const SpringBoneChainScript = preload("res://scripts/spring_bone_chain.gd")

@export var skeleton_path: NodePath

## Each entry: bone_name -> {stiffness, damping, gravity, drag, max_swing}
## Softer tissue (breast, belly) = lower stiffness, more gravity influence,
## more swing range. Glutes are firmer/denser tissue = higher stiffness,
## less swing. Hair clumps (once task 10's clump rig exists) get their own
## very different profile: coily/kinky hair holds its coil shape and moves
## in semi-rigid clusters rather than flowing like straight hair, so those
## entries use HIGH stiffness/damping and LOW gravity influence relative to
## soft tissue - they spring back to their coiled rest shape quickly instead
## of hanging loosely.
const PROFILES := {
	"breast_jiggle.L": {"stiffness": 0.55, "damping": 0.30, "gravity": 0.45, "drag": 0.06, "max_swing": 40.0},
	"breast_jiggle.R": {"stiffness": 0.55, "damping": 0.30, "gravity": 0.45, "drag": 0.06, "max_swing": 40.0},
	"belly_jiggle":    {"stiffness": 0.60, "damping": 0.35, "gravity": 0.35, "drag": 0.08, "max_swing": 30.0},
	"glute_jiggle.L":  {"stiffness": 0.75, "damping": 0.45, "gravity": 0.25, "drag": 0.10, "max_swing": 25.0},
	"glute_jiggle.R":  {"stiffness": 0.75, "damping": 0.45, "gravity": 0.25, "drag": 0.10, "max_swing": 25.0},
	# Hair clump defaults (applied to any bone matching "hair_clump_*" once
	# the clump rig from task 10 is built and its bone names are known).
	"_hair_clump_default": {"stiffness": 0.82, "damping": 0.55, "gravity": 0.15, "drag": 0.18, "max_swing": 55.0},
}

func _ready() -> void:
	var skeleton := get_node(skeleton_path) as Skeleton3D
	if skeleton == null:
		push_error("SpringBoneRig: skeleton_path does not point to a Skeleton3D")
		return

	for bone_name in PROFILES.keys():
		if bone_name.begins_with("_"):
			continue
		if skeleton.find_bone(bone_name) < 0:
			continue  # bone not present on this rig build yet, skip quietly
		_add_chain(skeleton, bone_name, PROFILES[bone_name])

	# Hair clumps: wire up anything matching the naming convention using the
	# shared default profile, so this doesn't need editing again once task
	# 10 lands - just make sure the clump bones are named hair_clump_*.
	for i in range(skeleton.get_bone_count()):
		var name := skeleton.get_bone_name(i)
		if name.begins_with("hair_clump_"):
			_add_chain(skeleton, name, PROFILES["_hair_clump_default"])

func _add_chain(skeleton: Skeleton3D, bone_name: String, profile: Dictionary) -> void:
	var chain := SpringBoneChainScript.new()
	chain.skeleton_path = get_path_to(skeleton)
	chain.bone_name = bone_name
	chain.stiffness = profile["stiffness"]
	chain.damping = profile["damping"]
	chain.gravity_influence = profile["gravity"]
	chain.drag = profile["drag"]
	chain.max_swing_degrees = profile["max_swing"]
	chain.name = "SpringBone_" + bone_name
	add_child(chain)
