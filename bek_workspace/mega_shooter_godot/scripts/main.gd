extends Node2D

@export var player_scene: PackedScene
@export var enemy_scene: PackedScene
@export var spawn_interval: float = 1.5

var score: int = 0
var game_over: bool = false
var spawn_timer: Timer

func _ready() -> void:
	spawn_timer = Timer.new()
	spawn_timer.wait_time = spawn_interval
	spawn_timer.autostart = true
	spawn_timer.timeout.connect(_on_spawn_timer_timeout)
	add_child(spawn_timer)

	var player = player_scene.instantiate()
	player.global_position = Vector2(400, 300)
	add_child(player)

func _on_spawn_timer_timeout() -> void:
	if game_over:
		return
	var enemy = enemy_scene.instantiate()
	enemy.global_position = Vector2(randf_range(100, 700), randf_range(100, 500))
	add_child(enemy)

func add_score(points: int) -> void:
	score += points

func _on_player_died() -> void:
	game_over = true
	spawn_timer.stop()
	print("Game Over! Score: ", score)