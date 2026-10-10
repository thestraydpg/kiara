@tool
extends SceneTree

## One-off builder: instances the imported kiara.glb, attaches the
## SpringBoneRig physics controller pointed at its Skeleton3D, and saves
## the result as scenes/kiara_character.tscn. Run via:
##   godot --headless --script tools/build_character_scene.gd

func _initialize() -> void:
	var glb_scene: PackedScene = load("res://assets/kiara.glb")
	if glb_scene == null:
		push_error("Could not load res://assets/kiara.glb")
		quit(1)
		return

	var root := Node3D.new()
	root.name = "KiaraCharacter"

	# get_path_to() requires both nodes to actually be inside a live
	# SceneTree (not just parented to each other off-tree), so attach to
	# the real root before computing any NodePaths.
	self.root.add_child(root)

	var glb_instance := glb_scene.instantiate()
	glb_instance.name = "Model"
	root.add_child(glb_instance)
	glb_instance.owner = root

	# find the Skeleton3D anywhere under the imported model
	var skeleton := _find_skeleton(glb_instance)
	if skeleton == null:
		push_error("No Skeleton3D found in imported model")
		quit(1)
		return
	print("Found skeleton: ", skeleton.get_path(), " bone_count=", skeleton.get_bone_count())

	# Compute the path from root's perspective (root is already live in the
	# tree) while spring_rig is still off-tree, then set skeleton_path
	# BEFORE add_child() - _ready() fires synchronously ON add_child(), so
	# setting the property afterward is too late and SpringBoneRig's
	# _ready() runs with an empty skeleton_path, silently failing to find
	# any bones.
	var path_from_root: NodePath = root.get_path_to(skeleton)
	var path_from_sibling := NodePath("../" + str(path_from_root))

	var spring_rig := Node.new()
	spring_rig.set_script(load("res://scripts/spring_bone_rig.gd"))
	spring_rig.name = "SpringBoneRig"
	spring_rig.set("skeleton_path", path_from_sibling)
	root.add_child(spring_rig)
	spring_rig.owner = root
	print("skeleton_path set to: ", path_from_sibling)

	# MCU bridge - same path-before-add_child ordering, same "../" depth
	# correction as spring_rig above (both are root's direct children).
	var mcu_bridge := Node.new()
	mcu_bridge.set_script(load("res://scripts/mcu_bridge.gd"))
	mcu_bridge.name = "MCUBridge"
	mcu_bridge.set("skeleton_path", path_from_sibling)
	root.add_child(mcu_bridge)
	mcu_bridge.owner = root

	# Only the instance's own root needs an owner for it to show up as a
	# child of our new scene - do NOT recurse into its internal children's
	# ownership. Setting owner on every node inside the glb hierarchy (as an
	# earlier version of this script did) flattens/duplicates all of that
	# mesh data directly into kiara_character.tscn instead of keeping it as
	# a lightweight reference to kiara.glb, bloating the file and breaking
	# the link to future GLB re-exports.
	spring_rig.owner = root
	glb_instance.owner = root

	var packed := PackedScene.new()
	var result := packed.pack(root)
	if result != OK:
		push_error("pack() failed: %s" % result)
		quit(1)
		return

	var save_path := "res://scenes/kiara_character.tscn"
	var err := ResourceSaver.save(packed, save_path)
	if err != OK:
		push_error("Save failed: %s" % err)
		quit(1)
		return

	print("Saved: ", save_path)
	quit(0)

func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node
	for child in node.get_children():
		var found := _find_skeleton(child)
		if found:
			return found
	return null
