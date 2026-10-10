extends Node
class_name MCUBridge

## Connects to the Python Kiara MCU server (mcu/server.py) over TCP and
## applies the incoming gesture/posture bone poses to the live skeleton
## every frame, on top of whatever the locomotion/idle base pose is doing.
##
## This bridge owns the EXPRESSIVE bones only (head, neck, arms, upper
## spine) - it never touches legs/pelvis, so it composes cleanly with
## the MuJoCo-trained locomotion retarget and the spring-bone jiggle
## physics without conflicting over the same bone.

@export var skeleton_path: NodePath
@export var host: String = "127.0.0.1"
@export var port: int = 8765
@export var reconnect_interval: float = 2.0

var _skeleton: Skeleton3D
var _tcp := StreamPeerTCP.new()
var _connected: bool = false
var _reconnect_timer: float = 0.0
var _recv_buffer: String = ""

func _ready() -> void:
	_skeleton = get_node(skeleton_path) as Skeleton3D
	if _skeleton == null:
		push_error("MCUBridge: skeleton_path does not point to a Skeleton3D")
	_try_connect()

func _try_connect() -> void:
	var err := _tcp.connect_to_host(host, port)
	if err != OK:
		push_warning("MCUBridge: connect_to_host failed: %s" % err)

func _process(_delta: float) -> void:
	_tcp.poll()
	var status := _tcp.get_status()

	if status == StreamPeerTCP.STATUS_CONNECTED:
		if not _connected:
			print("MCUBridge: connected to MCU server")
			_connected = true
		_pump_incoming()
	elif status == StreamPeerTCP.STATUS_ERROR or status == StreamPeerTCP.STATUS_NONE:
		if _connected:
			print("MCUBridge: disconnected")
		_connected = false
		_reconnect_timer -= _delta_safe()
		if _reconnect_timer <= 0.0:
			_reconnect_timer = reconnect_interval
			_try_connect()

func _delta_safe() -> float:
	return get_process_delta_time()

func _pump_incoming() -> void:
	var avail := _tcp.get_available_bytes()
	if avail <= 0:
		return
	var chunk := _tcp.get_utf8_string(avail)
	_recv_buffer += chunk
	while true:
		var nl := _recv_buffer.find("\n")
		if nl < 0:
			break
		var line := _recv_buffer.substr(0, nl)
		_recv_buffer = _recv_buffer.substr(nl + 1)
		if line.strip_edges() != "":
			_handle_line(line)

func _handle_line(line: String) -> void:
	var parsed = JSON.parse_string(line)
	if parsed == null or typeof(parsed) != TYPE_DICTIONARY:
		return
	if parsed.get("type") == "pose":
		_apply_pose(parsed.get("bones", {}))

func _apply_pose(bones: Dictionary) -> void:
	if _skeleton == null:
		return
	for bone_name in bones.keys():
		var idx := _skeleton.find_bone(bone_name)
		if idx < 0:
			continue
		var rot: Array = bones[bone_name]
		if rot.size() != 3:
			continue
		var euler := Vector3(deg_to_rad(rot[0]), deg_to_rad(rot[1]), deg_to_rad(rot[2]))
		var basis := Basis.from_euler(euler)
		_skeleton.set_bone_pose_rotation(idx, basis.get_rotation_quaternion())

## Send a command to the MCU (e.g. called by the brain/agent layer once
## it's wired in). Safe to call even if not currently connected.
func fire(function_name: String, params: Dictionary = {}) -> void:
	_send({"type": "fire", "name": function_name, "params": params})

func set_pad(pleasure: float, arousal: float, dominance: float) -> void:
	_send({"type": "pad", "pleasure": pleasure, "arousal": arousal, "dominance": dominance})

func _send(obj: Dictionary) -> void:
	if not _connected:
		return
	var line := JSON.stringify(obj) + "\n"
	_tcp.put_data(line.to_utf8_buffer())
