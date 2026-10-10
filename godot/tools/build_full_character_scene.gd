@tool
extends SceneTree

## Rebuilds scenes/kiara_character.tscn with a full playable rig on top
## of what build_character_scene.gd already set up (Model + SpringBoneRig
## + MCUBridge): a CharacterBody3D root with real collision, a follow
## camera, lighting, a ground plane, and the gamepad/touch/autonomy/
## teleop-logging input layer. Run via:
##   godot --headless --script tools/build_full_character_scene.gd

const SCRIPTS := "res://scripts/"

func _initialize() -> void:
	var glb_scene: PackedScene = load("res://assets/kiara.glb")
	if glb_scene == null:
		push_error("Could not load res://assets/kiara.glb")
		quit(1)
		return

	var root := CharacterBody3D.new()
	root.name = "KiaraCharacter"
	root.set_script(load(SCRIPTS + "locomotion_controller.gd"))
	# Her own collision capsule sits on a different physics layer than
	# world geometry (set below on Ground) specifically so CameraRig's
	# spring-arm collision avoidance - which by default tests against
	# layer 1, same as everything else - doesn't hit HER OWN capsule
	# first and collapse the camera down to ~0 length, landing it
	# inside her head. That's exactly what was happening before this:
	# the arm's pivot sits at head height, right inside her own capsule,
	# so without this separation it could never extend outward at all.
	root.collision_layer = 2
	root.collision_mask = 1
	self.root.add_child(root)

	var model := glb_scene.instantiate()
	model.name = "Model"
	root.add_child(model)
	model.owner = root

	# newly added nodes aren't considered "inside tree" for get_path()/
	# global_transform purposes until the engine has actually run a frame -
	# this bit twice already (empty get_path(), then an identity-transform
	# AABB silently merging every mesh's bounds as if all at the origin).
	await self.process_frame
	await self.process_frame

	var skeleton := _find_skeleton(model)
	if skeleton == null:
		push_error("No Skeleton3D found in imported model")
		quit(1)
		return
	print("Found skeleton: ", skeleton.get_path(), " bone_count=", skeleton.get_bone_count())

	var path_from_root: NodePath = root.get_path_to(skeleton)
	var path_from_sibling := NodePath("../" + str(path_from_root))

	# --- collision, fitted to the actual mesh bounds ---
	var aabb := _collect_aabb(model)
	var height: float = max(aabb.size.y, 1.0)
	var radius: float = clamp(min(aabb.size.x, aabb.size.z) * 0.5, 0.15, 0.35)
	var capsule := CapsuleShape3D.new()
	capsule.height = height
	capsule.radius = radius
	var coll := CollisionShape3D.new()
	coll.shape = capsule
	coll.name = "CollisionShape3D"
	coll.position = Vector3(0, aabb.position.y + height * 0.5, 0)
	root.add_child(coll)
	coll.owner = root
	print("Collision capsule: height=", height, " radius=", radius, " from aabb=", aabb)

	# Model's origin isn't at her feet (it's wherever the Blender rig's
	# root bone landed, mid-torso here) - without this she'd spawn with
	# her feet ~1m below the ground plane instead of standing on it.
	root.position.y = -aabb.position.y + 0.02

	# --- follow camera (GTA-style third person, driven by BodyIntent.look) ---
	var cam_rig := SpringArm3D.new()
	cam_rig.name = "CameraRig"
	cam_rig.set_script(load(SCRIPTS + "third_person_camera.gd"))
	cam_rig.position = Vector3(0, aabb.position.y + height * 0.82, 0)  # roughly head/shoulder height
	cam_rig.spring_length = 3.5
	cam_rig.rotation.y = PI  # if the camera starts facing her back instead of her front, flip this to 0
	root.add_child(cam_rig)
	cam_rig.owner = root

	var cam := Camera3D.new()
	cam.name = "Camera3D"
	cam.current = true
	cam_rig.add_child(cam)
	cam.owner = root

	# --- lighting + sky (the previous scene had neither, so running it
	# rendered a black screen with nothing visible) ---
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation = Vector3(deg_to_rad(-55), deg_to_rad(35), 0)
	sun.light_energy = 1.1
	root.add_child(sun)
	sun.owner = root

	var env_node := WorldEnvironment.new()
	env_node.name = "WorldEnvironment"
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.8
	env_node.environment = env
	root.add_child(env_node)
	env_node.owner = root

	# --- ground plane (otherwise CharacterBody3D free-falls forever - the
	# MuJoCo floor geom is a separate, unrelated simulation) ---
	var ground := StaticBody3D.new()
	ground.name = "Ground"
	ground.collision_layer = 1  # explicit: this is the layer CameraRig's spring-arm avoids
	ground.collision_mask = 0   # a StaticBody3D never moves, so it has nothing to detect
	var ground_coll := CollisionShape3D.new()
	var ground_shape := WorldBoundaryShape3D.new()
	ground_shape.plane = Plane(Vector3.UP, 0.0)
	ground_coll.shape = ground_shape
	ground.add_child(ground_coll)
	var ground_mesh := MeshInstance3D.new()
	var plane_mesh := PlaneMesh.new()
	plane_mesh.size = Vector2(40, 40)
	ground_mesh.mesh = plane_mesh
	ground.add_child(ground_mesh)
	self.root.add_child(ground)
	ground.owner = self.root
	ground_coll.owner = self.root
	ground_mesh.owner = self.root

	# --- physics rig (existing) ---
	var spring_rig := Node.new()
	spring_rig.set_script(load(SCRIPTS + "spring_bone_rig.gd"))
	spring_rig.name = "SpringBoneRig"
	spring_rig.set("skeleton_path", path_from_sibling)
	root.add_child(spring_rig)
	spring_rig.owner = root

	var mcu_bridge := Node.new()
	mcu_bridge.set_script(load(SCRIPTS + "mcu_bridge.gd"))
	mcu_bridge.name = "MCUBridge"
	mcu_bridge.set("skeleton_path", path_from_sibling)
	root.add_child(mcu_bridge)
	mcu_bridge.owner = root

	# --- new input / autonomy / learning layer ---
	var gamepad := Node.new()
	gamepad.name = "GamepadController"
	gamepad.set_script(load(SCRIPTS + "gamepad_controller.gd"))
	root.add_child(gamepad)
	gamepad.owner = root

	var touch := Node.new()
	touch.name = "TouchInteraction"
	touch.set_script(load(SCRIPTS + "touch_interaction.gd"))
	touch.set("camera_path", NodePath("../CameraRig/Camera3D"))
	root.add_child(touch)
	touch.owner = root

	var autonomy := Node.new()
	autonomy.name = "AutonomyDriver"
	autonomy.set_script(load(SCRIPTS + "autonomy_driver.gd"))
	root.add_child(autonomy)
	autonomy.owner = root

	var teleop := Node.new()
	teleop.name = "TeleopRecorder"
	teleop.set_script(load(SCRIPTS + "teleop_recorder.gd"))
	teleop.set("body_path", NodePath(".."))
	root.add_child(teleop)
	teleop.owner = root

	# now that the children referenced by path actually exist, wire root's
	# own exported paths (must be set before _ready - harmless here since
	# _ready only fires once this whole tree is packed/instanced later,
	# not during this headless build pass).
	root.set("visual_path", NodePath("Model"))
	root.set("camera_rig_path", NodePath("CameraRig"))
	root.set("touch_path", NodePath("TouchInteraction"))

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

func _collect_aabb(node: Node) -> AABB:
	var result := AABB()
	var first := true
	for mesh_inst in _find_all_mesh_instances(node):
		var local_aabb: AABB = mesh_inst.get_aabb()
		var xform: Transform3D = mesh_inst.global_transform
		var world_aabb := AABB(xform * local_aabb.position, Vector3.ZERO)
		for i in range(8):
			world_aabb = world_aabb.expand(xform * local_aabb.get_endpoint(i))
		if first:
			result = world_aabb
			first = false
		else:
			result = result.merge(world_aabb)
	return result

func _find_all_mesh_instances(node: Node) -> Array:
	var out: Array = []
	if node is MeshInstance3D:
		out.append(node)
	for child in node.get_children():
		out.append_array(_find_all_mesh_instances(child))
	return out
