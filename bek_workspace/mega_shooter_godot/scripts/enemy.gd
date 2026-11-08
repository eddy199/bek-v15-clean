extends CharacterBody2D

@export var speed: float = 200.0
var screen_size: Vector2

func _ready() -> void:
	screen_size = get_viewport_rect().size

func _physics_process(delta: float) -> void:
	position.y += speed * delta
	if position.y > screen_size.y + 50:
		queue_free()
