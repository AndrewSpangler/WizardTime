import math

def get_vector_between_entities(e1, e2) -> tuple[int, int]:
    dx = e1.x - e2.x
    dy = e1.y - e2.y
    angle = math.atan2(dx, dy)
    return (math.sin(angle), math.cos(angle))

def cap_velocity(x_vel, y_vel, max_vel):
    angle = math.atan2(y_vel, x_vel)
    new_x_vel = math.cos(angle) * max_vel
    new_y_vel = math.sin(angle) * max_vel
    return new_x_vel, new_y_vel

def detect_circle_collision(projectile, entity, overlap:float=0.0):
    dx = projectile.x - entity.x
    dy = projectile.y - entity.y
    distance = (dx**2 + dy**2)**0.5
    return distance <= (projectile.scale/3 + entity.scale[0]/2) * (1.0 - overlap * ((projectile.scale/3)/(entity.scale[0]/2)))

def detect_player_in_range(player, entity, following=False):
    dx = player.x - entity.x
    dy = player.y - entity.y
    distance = (dx**2 + dy**2)**0.5
    rng = entity.max_follow_range if following else entity.awareness_range
    return distance <= (player.scale[0]/3 + rng/2)
