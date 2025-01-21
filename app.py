import os
import time
import numpy as np
import ursina
import random

from include.camera import PlayerCamera
from include.player import Player
from include.shaders import ShaderCollection
from include.entities import FloatingFollower, EnemyManager
from include.projectiles import ProjectileManager

from panda3d.core import ShaderBuffer, GeomEnums

def generate_empty_shader_buffer(name, size):
    return ShaderBuffer(name, np.zeros(size, dtype=np.float32).tobytes(), GeomEnums.UH_static)

SHADER_CONFIG = {
    "grid"          : {"fragment":"grid.frag",          "vertex":"common.vert"},
    "canvas"        : {"fragment":"player.frag",        "vertex":"common.vert"},
    "projectiles"   : {"fragment":"projectiles.frag",   "vertex":"common.vert"},
    "awareness"     : {"fragment":"awareness.frag",     "vertex":"common.vert"},
    "enemies"       : {"fragment":"enemies.frag",       "vertex":"common.vert"},
}

class Game:
    def __init__(self, *args, **kwargs):
        # self.app = ursina.Ursina(*args, size=ursina.Vec2(2560,1440), **kwargs)
        self.app = ursina.Ursina(*args, size=ursina.Vec2(1920,1080), **kwargs)
        # self.app = ursina.Ursina(*args, size=ursina.Vec2(1280,720), **kwargs)
        self.start = time.time()

        self.player_projectiles = ProjectileManager(self)
        self.enemy_projectiles = ProjectileManager(self)
        self.enemies = EnemyManager(self)

        self.shader_collection = ShaderCollection(
            os.path.join(os.path.dirname(__file__), "shaders"),
            SHADER_CONFIG
        )

        # Quad layers
        # In order to layer different shaders efficiently and simplify z-layering for health bars etc,
        # Quads with different shaders are layered to create the final output display

        _layers = {
            "background" : {"color":ursina.color.dark_gray}, 
            "canvas" : {"shader":self.shader_collection.shaders["canvas"], "texture":"assets/wizard.png"},
            # "grid" : {"shader":self.shader_collection.shaders["grid"]},
            "enemies" : {"shader":self.shader_collection.shaders["enemies"], "texture":"assets/enemy.png"},
            "enemy_projectiles": {"shader":self.shader_collection.shaders["projectiles"], "texture":"assets/projectile.png"},
            "projectiles": {"shader":self.shader_collection.shaders["projectiles"], "texture":"assets/projectile.png"},
        }

        self.layers = {}
        for i, (name, conf) in list(enumerate(_layers.items())):
            self.layers[name] = ursina.Entity(
                model='quad',
                scale=((ursina.window.size[0]/ursina.window.size[1])*40, 40),
                collider=None,
                **conf,
            )
            self.layers[name].z = self.layers[name].z - 0.02 * i

        self.layers["canvas"].set_shader_input('background', loader.loadTexture("assets/cobble.png"))
        self.layers["canvas"].set_shader_input("count", 1)
        self.layers["canvas"].set_shader_input("screen_size", ursina.window.size)
        self.layers["canvas"].set_shader_input("drawableData", generate_empty_shader_buffer("drawableData", (1, 12)))

        self.layers["projectiles"].set_shader_input("count", len(self.player_projectiles.used_indicies))
        self.layers["projectiles"].set_shader_input("screen_size", ursina.window.size)
        self.layers["projectiles"].set_shader_input("projectileData", self.player_projectiles.ssbo)

        self.layers["enemy_projectiles"].set_shader_input("count", len(self.enemy_projectiles.used_indicies))
        self.layers["enemy_projectiles"].set_shader_input("screen_size", ursina.window.size)
        self.layers["enemy_projectiles"].set_shader_input("projectileData", self.player_projectiles.ssbo)

        self.layers["enemies"].set_shader_input("count", len(self.enemies.used_indicies))
        self.layers["enemies"].set_shader_input("screen_size", ursina.window.size)
        self.layers["enemies"].set_shader_input("drawableData", self.enemies.ssbo)

        # self.layers["awareness"].set_shader_input("positions", [[0,0,0]])
        # self.layers["awareness"].set_shader_input("radii", [5])
        # self.layers["awareness"].set_shader_input("circle_count", 0)
        # self.layers["awareness"].set_shader_input("screen_size", ursina.window.size)

        ## Uncomment for grid overlay
        # self.layers["grid"].set_shader_input("screen_size", ursina.window.size)
        # self.layers["grid"].set_shader_input("grid_spacing", 3)
        # self.layers["grid"].set_shader_input("grid_color", ursina.Vec4(1,1,1,1))
        # self.layers["grid"].set_shader_input("background_color", ursina.Vec4(0,0,0,0))    

        self.game_running = False
        self.paused = False

        self.enemy_entities = []
        self.game_entities = []
        self.orphan_projectiles = []
        self.ui_elements = {}
        self.sliders = {}
        self.show_sliders = False

        self.t = 0
        self.tick = 0

        self.start_game()
        self.create_sliders()

    def create_sliders(self):
        """Creates sliders to adjust game parameters."""
        slider_config = [
            {"name": "base_acceleration", "min": 0.1, "max": 4, "default": 0.6, "position": (0.25, 0.4), "origin":(1,0), "scale":0.4},
            {"name": "max_velocity", "min": 10, "max": 500.0, "default": 130, "position": (0.25, 0.35), "origin":(1,0), "scale":0.4},
            {"name": "min_velocity", "min": 0.01, "max": 4.0, "default": 0.08, "position": (0.25, 0.3), "origin":(1,0), "scale":0.4},
            {"name": "decay_rate", "min": 0.001, "max": 0.1, "default": 0.04, "position": (0.25, 0.25), "origin":(1,0), "scale":0.4},
            {"name": "fire_rate", "min": 0.5, "max": 200, "default": 2, "position": (0.25, 0.2), "origin":(1,0), "scale":0.4},
            {"name": "projectile_decay_rate", "min": 0.01, "max": 0.03, "default": 0.01, "position": (0.25, 0.15), "origin":(1,0), "scale":0.4},
            {"name": "projectile_speed_multiplier", "min": 0.5, "max": 50, "default": 2, "position": (0.25, 0.1), "origin":(1,0), "scale":0.4},
            {"name": "range", "min": 1, "max": 5, "default": 1.5, "position": (0.25, 0.05), "origin":(1,0), "scale":0.4},
        ]

        for config in slider_config:
            slider = ursina.Slider(
                min=config["min"],
                max=config["max"],
                value=config["default"],
                step=0.01,
                text=f"{config['name']}: {config['default']:.2f}",
                position=config["position"]
            )
            self.sliders[config["name"]] = slider
            slider.hide()

        def toggle_sliders():
            self.show_sliders = not self.show_sliders
            if self.show_sliders:
                for n, s in self.sliders.items():
                    s.show()
            else:
                for n, s in self.sliders.items():
                    s.hide()
        
        b = ursina.Button(text="Show Sliders", position = (0.65, 0.45), scale=(0.2, 0.04))
        b.on_click = toggle_sliders

    def start_game(self):
        self.game_running = True
        self.paused = False
        self.game_entities = [
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(69, 5, 1), position=(0,22,0), collider=None),
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(69, 5, 1), position=(0,-22,0), collider=None),
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(7, 50, 1), position=(38,0,0), collider=None),
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(7, 50, 1), position=(-38,0,0), collider=None),
        ]
        self.player = Player(game=self, x=0, y=0)
        ec = PlayerCamera()

        # Initialize UI elements
        start_x = -0.875
        start_y = 0.475
    
        for name, conf in {
            "x" :                {"text":f"x: {self.player.x}"},
            "y" :                {"text":f"y: {self.player.y}"},
            "x_vel":             {"text":f"x_velocity: {self.player.x_velocity}"},
            "y_vel":             {"text":f"y_velocity: {self.player.y_velocity}"},
            "total_vel":         {"text":f"total_velocity: {self.player.total_velocity}"},
            "projectile_count":  {"text":f"projectile_count: {len(self.player_projectiles.used_indicies)}"},
            "enemy_count":       {"text":f"enemy_count: {len(self.enemies.used_indicies)}"},
            "enemy_projectile_count":  {"text":f"enemy_projectile_count: {len(self.enemy_projectiles.used_indicies)}"},
        }.items():
            self.ui_elements[name] = ursina.Text(
                conf.pop("text"),
                **conf,
                position = (start_x, start_y),
                origin = (-0.5,0)
            )
            start_y -= 0.05

        for i in range(-11,11):
            for j in range(-7,7):
                if not i % 4 and not j % 4:
                    self.spawn_creature(FloatingFollower, config={"x":i,"y":j})

    def handle_player_bounds(self):
        bounds = (13,23)
        half_height = bounds[0]*1.5
        half_width  = bounds[1]*1.5
        half_y = self.player.scale_y / 2
        half_x = self.player.scale_x / 2
        if self.player.x - half_x < -half_width:
            self.player.x = -half_width + half_x
            self.player.x_velocity = 0
        elif self.player.x + half_x > half_width:
            self.player.x = half_width - half_x
            self.player.x_velocity = 0
        if self.player.y - half_y < -half_height:
            self.player.y = -half_height + half_y
            self.player.y_velocity = 0
        elif self.player.y + half_y > half_height:
            self.player.y = half_height - half_y
            self.player.y_velocity = 0

    def handle_player_projectile_collisions(self):
        to_despawn = set()
        for i in list(self.enemies.used_indicies):
            collisions = self.player_projectiles.check_collisions(self.enemies.data[i, 0:2], (self.enemies.data[i, 3],))
            to_despawn.update(collisions)
            for c in collisions:
                if self.enemies.data[i, 19] > 0:
                    self.enemies.data[i, 19] = max(0, self.enemies.data[i, 19]-5)
                else:
                    self.enemies.data[i, 18] = max(0, self.enemies.data[i, 18] - 5)
                if self.enemies.data[i, 18] <= 0:
                    self.enemies.despawn(i)

        self.player_projectiles.despawn_multiple(to_despawn)

    def handle_enemy_projectile_collisions(self):
        collisions = self.enemy_projectiles.check_collisions(self.player.position2d, self.player.scale)
        for c in collisions:
            continue
            # if self.player.shield > 0:
            #     self.player.shield = max(0, self.player.shield-5)
            # else:
            #     self.player.health = max(0, self.player.health - 5)
            # if self.player.health <= 0:
            #     raise ValueError("YOU DIED")
        self.enemy_projectiles.despawn_multiple(collisions)

    def update_ui(self):
        # Update UI elements with player's current status
        for n, text in {
            "x" :                f"x: {self.player.x:.2f}",
            "y" :                f"y: {self.player.y:.2f}",
            "x_vel":             f"x_velocity: {self.player.x_velocity:.2f}",
            "y_vel":             f"y_velocity: {self.player.y_velocity:.2f}",
            "total_vel":         f"total_velocity: {self.player.total_velocity:.2f}",
            "projectile_count":  f"projectile_count: {len(self.player_projectiles.used_indicies)}",
            "enemy_count":       f"enemy_count: {len(self.enemies.used_indicies)}",
            "enemy_projectile_count":  f"enemy_projectile_count: {len(self.enemy_projectiles.used_indicies)}",
        }.items():
            self.ui_elements[n].text = text
        # Update sliders
        self.player.base_acceleration = self.sliders["base_acceleration"].value
        self.player.max_velocity = self.sliders["max_velocity"].value
        self.player.min_velocity = self.sliders["min_velocity"].value
        self.player.decay_rate = self.sliders["decay_rate"].value
        self.player.fire_rate = self.sliders["fire_rate"].value
        self.player.projectile_decay_rate = self.sliders["projectile_decay_rate"].value
        self.player.projectile_speed_multiplier = self.sliders["projectile_speed_multiplier"].value
        self.player.range = self.sliders["range"].value
        # Update slider text
        for name, slider in self.sliders.items():
            slider.text = f"{name}: {slider.value:.2f}"

    def update(self):
        if not all((self.game_running, not self.paused)):
            return
        
        self.t += ursina.time.dt
        
        # Handle physics
        self.player.handle_movement()
        self.player.handle_projectile()
        self.handle_player_bounds()
        self.player_projectiles.update()
        self.enemies.update()
        self.enemies.resolve_external_overlap(self.player.position2d, self.player.scale[0])
        self.enemy_projectiles.update()
        self.handle_player_projectile_collisions()
        self.handle_enemy_projectile_collisions()

        # Write shader data
        self.player.update_ssbo()
        self.layers["canvas"].set_shader_input("drawableData", self.player.ssbo)
    
        self.layers["projectiles"].set_shader_input("count", len(self.player_projectiles.used_indicies))
        self.layers["projectiles"].set_shader_input("projectileData", self.player_projectiles.ssbo)
              
        self.layers["enemy_projectiles"].set_shader_input("count", len(self.enemy_projectiles.used_indicies))
        self.layers["enemy_projectiles"].set_shader_input("projectileData", self.enemy_projectiles.ssbo)

        self.layers["enemies"].set_shader_input("count", len(self.enemies.used_indicies))
        self.layers["enemies"].set_shader_input("drawableData", self.enemies.ssbo)
        
        if not self.tick % 130:
            self.spawn_creature(FloatingFollower, config={"x":random.randint(-11,11),"y":random.randint(-6,6)})

        if not self.tick % 60:
            self.update_ui()

        self.tick += 1


    def end_game(self):
        self.game_running = False
        self.paused = False
        for e in self.game_entities:
            e.destroy()
        for ui in self.ui_elements.values():
            ui.disable()

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def toggle_pause(self):
        self.paused = not self.paused

    def spawn_creature(self, creature:object, config:dict={}):
        self.enemies.spawn(creature, ursina.Vec2(config.get("x"), config.get("y")))

game = Game()
update = game.update
ursina.window.exit_button.enabled = True
ursina.window.vsync = 60
ursina.window.center_on_screen()
ursina.camera.orthographic = True
ursina.camera.fov = 10
game.app.run()