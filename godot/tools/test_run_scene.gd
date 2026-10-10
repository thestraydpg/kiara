extends SceneTree

## Loads kiara_character.tscn, runs it for a handful of physics frames, and
## reports whether the spring-bone chains are actually simulating (bone
## poses changing frame to frame) without errors. Run via:
##   godot --headless --script tools/test_run_scene.gd

var _frame_count := 0
var _skeleton: Skeleton3D
var _test_bone_idx := -1
var _last_rotation: Quaternion

func _initialize() -> void:
	var packed: PackedScene = load("res://scenes/kiara_character.tscn")
	if packed == null:
		push_error("Could not load kiara_character.tscn")
		quit(1)
		return
	var instance := packed.instantiate()
	root.add_child(instance)

	_skeleton = _find_skeleton(instance)
	if _skeleton == null:
		push_error("No skeleton found in instanced scene")
		quit(1)
		return

	_test_bone_idx = _skeleton.find_bone("breast_jiggle.L")
	print("Test bone 'breast_jiggle.L' index: ", _test_bone_idx)
	print("Scene instanced OK, bone count: ", _skeleton.get_bone_count())

	var spring_rig := instance.get_node("SpringBoneRig")
	print("SpringBoneRig children (active spring chains): ", spring_rig.get_child_count())

func _process(delta: float) -> bool:
	_frame_count += 1
	if _test_bone_idx >= 0:
		var pose := _skeleton.get_bone_pose_rotation(_test_bone_idx)
		if _frame_count == 5:
			_last_rotation = pose
		elif _frame_count > 5 and _frame_count % 10 == 0:
			var changed := not pose.is_equal_approx(_last_rotation)
			print("Frame ", _frame_count, " breast_jiggle.L rotation changed since frame 5: ", changed, "  rot=", pose)
	if _frame_count >= 40:
		print("Test complete, no crashes over ", _frame_count, " frames")
		quit(0)
		return true
	return false

func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node
	for child in node.get_children():
		var found := _find_skeleton(child)
		if found:
			return found
	return null
