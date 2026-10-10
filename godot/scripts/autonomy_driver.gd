extends Node
class_name AutonomyDriver

## When nobody is actively driving BodyIntent (no gamepad/touch input for
## BodyIntent.IDLE_TIMEOUT seconds), this writes a gentle self-directed
## idle intent instead - a slow wander + occasional pause - so she's never
## just a lifeless statue waiting for input.
##
## Deliberately simple on purpose: a reflexive "idle fidget" loop, not
## cognition. Wiring this to an actual decision-making brain (MuJoCo
## policy selection, PAD-driven behavior, goals) is later-session work -
## see agent/ and mcu/ for where that plugs in. This script only ever
## writes to BodyIntent when BodyIntent.is_player_driving() is false, so
## it never has to coordinate with or fight the input sources themselves.

var _state_timer: float = 0.0
var _wander_dir: Vector2 = Vector2.ZERO
var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	_rng.randomize()
	_pick_new_wander()

func _process(delta: float) -> void:
	if BodyIntent.is_player_driving():
		return
	_state_timer -= delta
	if _state_timer <= 0.0:
		_pick_new_wander()
	BodyIntent.move = _wander_dir
	BodyIntent.look = Vector2.ZERO
	BodyIntent.sprint = false
	BodyIntent.jump = false

func _pick_new_wander() -> void:
	if _rng.randf() < 0.4:
		_wander_dir = Vector2.ZERO          # pause / idle
		_state_timer = _rng.randf_range(2.0, 5.0)
	else:
		var angle := _rng.randf_range(0, TAU)
		_wander_dir = Vector2(cos(angle), sin(angle)) * 0.4   # gentle walk, never sprint
		_state_timer = _rng.randf_range(1.5, 4.0)
