import ursina
import time
import math
import numpy as np
from panda3d.core import ShaderBuffer, GeomEnums
from .physics import cap_velocity


DIAG_MOVE_MULTIPLIER = math.sqrt(0.5)

MOVEMENT_KEYS = [
    ("s", "w"),
    ("a", "d")
]

FIRE_KEYS = [
    ("down arrow", "up arrow"),
    ("left arrow", "right arrow")
]
FIRE_KEYS_UNPACKED = [
    *FIRE_KEYS[0],
    *FIRE_KEYS[1]
]

class Player():
    def __init__(self, game, **kwargs):
        # super().__init__(collider=None)
        self.game = game
        self.x = 0
        self.y = 0
        self.z = 0

        self.origin_y = 0
        self.scale = 3
        self.color = ursina.color.white

        self.max_health = 100
        self.max_shield = 100
        self.health = 100
        self.shield = 100

        self.base_acceleration = 10
        self.max_velocity = 20
        self.min_velocity = 0.08
        self.decay_rate = 0.04

        self.teleport_cooldown = 2.5 
        self.next_teleport = time.time()

        self.portal_cooldown = 2.5 
        self.next_portal = time.time()

        self.range = 2
        self.fire_rate = 22
        self.projectile_decay_rate = 0.01
        self.projectile_speed_multiplier = 1
        self.base_projectile_speed = 40
        self.next_shot = time.time()
        self.held_keys = []

        self.x_velocity = 0
        self.moving_x = False
        self.y_velocity = 0
        self.moving_y = False
        self.total_velocity = 0
        self.fired_projectiles = []

        self.face_direction = 0

        # Buffer for shader data
        self._buffer = np.zeros((1, 12), dtype=np.float32)

        # self.eyes = [
        #     ursina.Entity(model='circle', scale=.1, parent=self, color=ursina.color.black, x=0, y=0, z=-1, origin_y=-2, origin_x=2),
        #     ursina.Entity(model='circle', scale=.1, parent=self, color=ursina.color.black, x=0, y=0, z=-1, origin_y=-2, origin_x=-2)
        # ]

        # self.hand = ursina.Entity(model='quad', scale=.35, texture="ball.png", color=ursina.color.green, x=0, y=0, z=-0.95, origin_y=-1)
        # self.hand.alpha = 0.5

        # self.ignore_list = [self, self.hand]
        
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.ssbo = None 
        self.update_ssbo()
    
    def update_ssbo(self):
        self._buffer[:] = (
            self.x,
            self.y,
            self.scale,
            self.face_direction,
            *self.color,
            self.max_health,
            self.max_shield,
            self.health,
            self.shield
        )
        self.ssbo = ShaderBuffer("PlayerData", self._buffer.tobytes(), GeomEnums.UH_static)

    @property
    def position2d(self):
        return ursina.Vec2(self.x, self.y)

    def handle_movement(self, dt):
        self.moving_y = any(ursina.held_keys[k] for k in MOVEMENT_KEYS[0])
        self.moving_x = any(ursina.held_keys[k] for k in MOVEMENT_KEYS[1])

        move_multiplier = DIAG_MOVE_MULTIPLIER if self.moving_x and self.moving_y else 1

        y_acc = (
            self.base_acceleration
            * move_multiplier
            * int(self.moving_y)
            * (1 if ursina.held_keys[MOVEMENT_KEYS[0][1]] else -1)
        )
        x_acc = (
            self.base_acceleration
            * move_multiplier
            * int(self.moving_x)
            * (1 if ursina.held_keys[MOVEMENT_KEYS[1][1]] else -1)
        )

        # Set eye position
        # angle=math.atan2(x_acc, y_acc)
        # for e in self.eyes:
        #     e.rotation_z = angle*180/math.pi

        self.y_velocity = max(-self.max_velocity, min(self.max_velocity, self.y_velocity + y_acc))
        self.x_velocity = max(-self.max_velocity, min(self.max_velocity, self.x_velocity + x_acc))

        total_vel = math.sqrt(
            self.y_velocity * self.y_velocity
            + self.x_velocity * self.x_velocity
        )

        if total_vel > self.max_velocity:
            self.x_velocity, self.y_velocity = cap_velocity(self.x_velocity, self.y_velocity, self.max_velocity)

        if total_vel < self.min_velocity and not (self.moving_x or self.moving_y): 
            self.x_velocity = 0
            self.y_velocity = 0
            
        self.x_velocity = self.x_velocity * (1-self.decay_rate)
        self.y_velocity = self.y_velocity * (1-self.decay_rate)

        self.total_velocity = math.sqrt(
            self.y_velocity * self.y_velocity
            + self.x_velocity * self.x_velocity
        )

        self.x += self.x_velocity * ursina.time.dt
        self.y += self.y_velocity * ursina.time.dt

    def handle_projectile(self):
        shooting_y = any(ursina.held_keys[k] for k in FIRE_KEYS[0])
        shooting_x = any(ursina.held_keys[k] for k in FIRE_KEYS[1])
        if not (shooting_x or shooting_y):
            return
        pressed_keys = [
            *[k for k in FIRE_KEYS[0] if ursina.held_keys[k]],
            *[k for k in FIRE_KEYS[1] if ursina.held_keys[k]],
        ]
        new_held_keys = [k for k in pressed_keys if not k in self.held_keys]
        if new_held_keys:
            new_held_key = new_held_keys[0]
            self.face_direction = FIRE_KEYS_UNPACKED.index(new_held_key)
        self.held_keys = new_held_keys
        # angle=math.atan2(*[[0,-1], [0,1], [-1,0], [1,0]][self.face_direction])
        
        # self.hand.rotation_z = angle*180/math.pi
        now = time.time()
        if self.next_shot < now:
            self.fire_projectile()
            self.next_shot = now + (1.0 / self.fire_rate)
    
    def fire_projectile(self):
        options = [[0,-1], [0,1], [-1,0], [1,0]]
        x_vel, y_vel = options[self.face_direction]
        vel = (
                x_vel * self.base_projectile_speed + self.x_velocity,
                y_vel * self.base_projectile_speed + self.y_velocity,
            )
        self.game.player_projectiles.spawn(
            position=(self.x, self.y),
            velocity=vel,
            _range = self.range,
            decay = self.projectile_decay_rate, 
        )

    def update(self):
        pass