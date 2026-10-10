extends Node
class_name RetargetBridge

## Connects to mujoco/retarget_server.py over TCP and applies the
## incoming MuJoCo-trained pose to her REAL skeleton every frame - the
## "watch the real her move with the trained physics" payoff, distinct
## from view.py's capsule/skin overlay inside MuJoCo's own viewer.
##
## Owns pelvis + full spine chain + neck/head + arms + legs - everything
## the locomotion/balance retarget touches. That's a deliberately large
## scope overlapping what MCUBridge documents as its own (arms, upper
## spine, head) - if both are connected and driving at once they will
## fight over those bones, same as any two systems writing the same
## bone in the same frame. Today that's an acceptable, known tension
## (in practice only one of "authored gesture" or "trained locomotion
## retarget" is likely to be live at a time); resolving it for real -
## blending, priority, or a shared owner - is later-session work once
## an actual brain exists to decide which one should win when.
##
## Does NOT touch position/root motion (that stays LocomotionController's
## job) - only bone pose ROTATIONS, received as direct quaternions
## (never Euler angles - this avoids needing retarget_server.py to match
## Godot's default Euler axis order exactly, which has no way to be
## visually checked from a sandbox with no display).

@export var skeleton_path: NodePath
@export var host: String = "127.0.0.1"
@export var port: int = 8766
@export var reconnect_interval: float = 2.0

var _skeleton: Skeleton3D
var _tcp := StreamPeerTCP.new()
var _connected: bool = false
var _reconnect_timer: float = 0.0
var _recv_buffer: String = ""

func _ready() -> void:
	_skeleton = get_node(skeleton_path) as Skeleton3D
	if _skeleton == null:
		push_error("RetargetBridge: skeleton_path does not point to a Skeleton3D")
	_try_connect()

func _try_connect() -> void:
	var err := _tcp.connect_to_host(host, port)
	if err != OK:
		push_warning("RetargetBridge: connect_to_host failed: %s" % err)

func _process(delta: float) -> void:
	_tcp.poll()
	var status := _tcp.get_status()

	if status == StreamPeerTCP.STATUS_CONNECTED:
		if not _connected:
			print("RetargetBridge: connected to retarget_server.py")
			_connected = true
		_pump_incoming()
	elif status == StreamPeerTCP.STATUS_ERROR or status == StreamPeerTCP.STATUS_NONE:
		if _connected:
			print("RetargetBridge: disconnected")
		_connected = false
		_reconnect_timer -= delta
		if _reconnect_timer <= 0.0:
			_reconnect_timer = reconnect_interval
			_try_connect()

func _pump_incoming() -> void:
	var avail := _tcp.get_available_bytes()
	if avail <= 0:
		return
	_recv_buffer += _tcp.get_utf8_string(avail)
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
		var q: Array = bones[bone_name]
		if q.size() != 4:
			continue
		_skeleton.set_bone_pose_rotation(idx, Quaternion(q[0], q[1], q[2], q[3]))
