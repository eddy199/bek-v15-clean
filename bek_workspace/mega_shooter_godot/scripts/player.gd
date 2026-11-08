extends CharacterBody2D

@export var speed: float = 400.0
@export var shoot_cooldown: float = 0.2
@export var bullet_scene: PackedScene

var cooldown_timer: float = 0.0

func _physics_process(delta: float) -> void:
	var velocity: Vector2 = Vector2.ZERO

	if Input.is_action_pressed("ui_right"):
		velocity.x += 1.0
	if Input.is_action_pressed("ui_left"):
		velocity.x -= 1.0
	if Input.is_action_pressed("ui_down"):
		velocity.y += 1.0
	if Input.is_action_pressed("ui_up"):
		velocity.y -= 1.0

	velocity = velocity.normalized() * speed
	move_and_slide()

	if cooldown_timer > 0.0:
		cooldown_timer -= delta

	if Input.is_key_just_pressed(KEY_SPACE) and cooldown_timer <= 0.0:
		shoot()

func shoot() -> void:
	if bullet_scene == null:
		return

	var bullet: Node2D = bullet_scene.instantiate()
	bullet.global_position = global_position
	get_tree().current_scene.add_child(bullet)

	cooldown_timer = shoot_cooldown