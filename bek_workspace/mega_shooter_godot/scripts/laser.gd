extends CharacterBody2D

const SPEED := 400.0
const SCREEN_TOP := -50.0

func _physics_process(delta: float) -> void:
	position += Vector2.UP * SPEED * delta
	if position.y < SCREEN_TOP:
		queue_free()
