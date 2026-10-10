extends SceneTree

## Connects an MCUBridge to a fresh instance of the character, waits for
## the TCP connection to the Python MCU server, fires "wave", and polls
## the upperarm.R bone pose over several frames to confirm the bridge is
## actually receiving and applying poses from the live server.
## Run with the MCU server already running (python3 mcu/server.py):
##   godot --headless --script tools/test_mcu_bridge.gd

const MCUBridgeScript = preload("res://scripts/mcu_bridge.gd")

var _skeleton: Skeleton3D
var _bridge: Node
var _frame := 0
var _fired := false

func _initialize() -> void:
	var glb_scene: PackedScene = load("res://assets/kiara.glb")
	var instance := glb_scene.instantiate()
	root.add_child(instance)
	_skeleton = _find_skeleton(instance)
	print("Skeleton found, bones: ", _skeleton.get_bone_count())

	# skeleton_path must be set BEFORE add_child() since _ready() fires
	# synchronously on add_child(); and since bridge will be root's child
	# (same depth as instance), the path needs one extra "../" beyond
	# what root.get_path_to() returns for root's own position.
	var path_from_root: NodePath = root.get_path_to(_skeleton)
	var bridge_path := NodePath("../" + str(path_from_root))

	_bridge = Node.new()
	_bridge.set_script(MCUBridgeScript)
	_bridge.skeleton_path = bridge_path
	root.add_child(_bridge)
	print("bridge skeleton_path: ", bridge_path)

func _process(delta: float) -> bool:
	_frame += 1
	if _frame == 30 and not _fired:
		print("Firing 'wave'...")
		_bridge.fire("wave", {"side": "R"})
		_fired = true
	if _frame > 30 and _frame % 15 == 0:
		var idx := _skeleton.find_bone("upperarm.R")
		var pose := _skeleton.get_bone_pose_rotation(idx)
		print("Frame ", _frame, " upperarm.R rotation: ", pose)
	if _frame >= 150:
		print("Test complete")
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
