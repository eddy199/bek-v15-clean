extends Node2D

@export var star_count: int = 100
@export var scroll_speed: float = 50.0
@export var star_color: Color = Color.WHITE

var stars: Array[Vector2] = []
var star_sizes: Array[float] = []

func _ready() -> void:
    _randomize_stars()

func _process(delta: float) -> void:
    var viewport_size: Vector2 = get_viewport_rect().size
    for i in star_count:
        stars[i].y += scroll_speed * delta
        if stars[i].y > viewport_size.y:
            stars[i].y = -star_sizes[i]
            stars[i].x = randf_range(0.0, viewport_size.x)
    queue_redraw()

func _draw() -> void:
    for i in star_count:
        draw_rect(Rect2(stars[i], Vector2(star_sizes[i], star_sizes[i])), star_color)

func _randomize_stars() -> void:
    var viewport_size: Vector2 = get_viewport_rect().size
    stars.resize(star_count)
    star_sizes.resize(star_count)
    for i in star_count:
        stars[i] = Vector2(randf_range(0.0, viewport_size.x), randf_range(0.0, viewport_size.y))
        star_sizes[i] = randf_range(1.0, 2.5)
