extends CharacterBody2D

class_name Player

@export var speed: float = 400.0
@export var shoot_cooldown: float = 0.2
@export var bullet_scene: PackedScene
@export var muzzle_position: Node2D

signal health_changed(current_health, max_health)
signal died

var health: int = 100
var max_health: int = 100
var _cooldown_timer: float = 0.0

func _physics_process(delta: float) -> void:
	var input_dir := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = input_dir * speed
	move_and_slide()

	if _cooldown_timer > 0:
		_cooldown_timer -= delta

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		shoot()

func shoot() -> void:
	if _cooldown_timer > 0:
		return
	if bullet_scene == null or muzzle_position == null:
		return

	var bullet := bullet_scene.instantiate()
	get_tree().root.add_child(bullet)
	bullet.global_position = muzzle_position.global_position

	var direction := (get_global_mouse_position() - muzzle_position.global_position).normalized()
	bullet.linear_velocity = direction * 800.0

	_cooldown_timer = shoot_cooldown

func take_damage(amount: int) -> void:
	health = clamp(health - amount, 0, max_health)
	health_changed.emit(health, max_health)
	if health <= 0:
		died.emit()
		queue_free()