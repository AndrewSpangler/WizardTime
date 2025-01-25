import os
import time
import numpy as np
import ursina

from include.camera import PlayerCamera
from include.player import Player
from include.shaders import ShaderCollection
from include.entities import FloatingFollower, EnemyManager
from include.projectiles import ProjectileManager
from include.portals import PortalManager
from include.buttons import ButtonManager

from panda3d.core import ShaderBuffer, GeomEnums

def generate_empty_shader_buffer(name, size):
    return ShaderBuffer(name, np.zeros(size, dtype=np.float32).tobytes(), GeomEnums.UH_static)

SHADER_CONFIG = {
    "canvas"        : {"fragment":"canvas.frag",        "vertex":"common.vert"},
}

class Game:
    def __init__(self, *args, **kwargs):
        # self.app = ursina.Ursina(*args, size=ursina.Vec2(2560,1440), **kwargs)
        # self.app = ursina.Ursina(*args, size=ursina.Vec2(1920,1080), **kwargs)
        self.app = ursina.Ursina(*args, size=ursina.Vec2(1280,720), **kwargs)
        self.start = time.time()
        self.player = Player(game=self, x=0, y=0)
        ec = PlayerCamera()
        self.player_projectiles = ProjectileManager(self, "Player")
        self.enemy_projectiles = ProjectileManager(self, "Enemy")
        self.enemies = EnemyManager(self, "Enemy")
        self.buttons = ButtonManager(self, "Button")
        self.portal_manager = PortalManager(self)
        self.portal_manager.add_portal_pair((15,-15), 6, ursina.color.red, (-15,15), 6, ursina.color.green)
        self.portal_manager.update_ssbo()

        self.shader_collection = ShaderCollection(
            os.path.join(os.path.dirname(__file__), "shaders"),
            SHADER_CONFIG
        )

        self.profiler_data = {}
        self.info_display = ursina.Text(text='', position=(-0.85, 0.4), scale=1, color=ursina.color.white, collider=None)
        # quads with different shaders are layered to create the final output display
        _layers = {
            # "background" : {"color":ursina.color.dark_gray}, 
            "canvas" : {"shader":self.shader_collection.shaders["canvas"], "texture":"assets/wizard.png"},
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

        self.gravity = 0

        # textures to be supplied to the shader
        self.textures = {
            'background_texture'    : "assets/cobble.png",
            'portal_texture'        : "assets/ball.png",
            'projectile_texture'    : "assets/projectile.png",
            'enemy_texture'         : "assets/enemy.png",
        }
        for name, tex in self.textures.items():
            self.layers["canvas"].set_shader_input(name, loader.loadTexture(tex))

        # shader buffers to write to the shader
        # since the ref to a given SSBO can be updated
        # the base of each ssbo is mapped below
        self.ssbo_parents = {
            "portalData"            : self.portal_manager,
            "EnemyProjectileData"   : self.enemy_projectiles,
            "PlayerProjectileData"  : self.player_projectiles,
            "EnemyData"             : self.enemies,
            "PlayerData"            : self.player,
        }
        for name, base in self.ssbo_parents.items():
            self.layers["canvas"].set_shader_input(name, base.ssbo)

        # calc grid spacing and offset based on screen resolution

        grid_spacing:float = 6
        grid_offset:float = 0.0
        print(grid_spacing, grid_offset)

        # general shader data
        for key, val in {
            "screen_size"               : ursina.window.size,
            "background_color"          : ursina.Vec4(0,0,0,0),
            "grid_spacing"              : grid_spacing,
            "grid_offset"               : grid_offset,
            "grid_color"                : ursina.Vec4(1,1,1,1),
            "count"                     : 1,
            "portal_count"              : self.portal_manager.max_portal_pairs,
            "enemy_count"               : np.count_nonzero(self.enemies.used_mask),
            "player_projectile_count"   : 0,
            "enemy_projectile_count"    : 0,    
        }.items():
            self.layers["canvas"].set_shader_input(key, val)

        # self.layers["awareness"].set_shader_input("positions", [[0,0,0]])
        # self.layers["awareness"].set_shader_input("radii", [5])
        # self.layers["awareness"].set_shader_input("circle_count", 0)
        # self.layers["awareness"].set_shader_input("screen_size", ursina.window.size)

        self.game_running = False
        self.paused = False

        self.enemy_entities = []
        self.game_entities = []
        self.orphan_projectiles = []
        self.ui_elements = {}
        self.sliders = {}
        self.show_sliders = True
        self.show_info = True

        self.t = 0
        self.tick = 0
        self.create_sliders()
        self.start_game()
        

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
            {"name": "gravity", "min": -2, "max": 2, "default": 0, "position": (0.25, 0.00), "origin":(1,0), "scale":0.4},
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

        b = ursina.Button(text="Show Sliders", position = (0.65, 0.45), scale=(0.2, 0.04))
        b.on_click = self.toggle_sliders

        b = ursina.Button(text="Show Info", position = (0.45, 0.45), scale=(0.2, 0.04))
        b.on_click = self.toggle_info

    def toggle_sliders(self):
        self.show_sliders = not self.show_sliders
        if self.show_sliders:
            for n, s in self.sliders.items():
                s.show()
        else:
            for n, s in self.sliders.items():
                s.hide()
    
    def toggle_info(self):
        self.show_info = not self.show_info
        if self.show_info:
            self.info_display.show()
        else:
            self.info_display.hide()    

    def start_game(self):
        self.game_running = True
        self.paused = False
        self.game_entities = [
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(69, 5, 1), position=(0,22,0), collider=None),
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(69, 5, 1), position=(0,-22,0), collider=None),
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(7, 50, 1), position=(38,0,0), collider=None),
            ursina.Entity(model='cube', color=ursina.color.white33, scale=(7, 50, 1), position=(-38,0,0), collider=None),
        ]
        for i in range(-11,11):
            for j in range(-7,7):
                # if not i % 3 and not j % 3:
                self.spawn_creature(FloatingFollower, config={"x":i,"y":j})
        self.show_info = False
        self.update_ui()
        self.toggle_info()
        self.last_update = time.time()

    def handle_player_bounds(self):
        bounds = (13, 23)
        half_height = bounds[0] * 1.5
        half_width = bounds[1] * 1.5
        player_x, player_y = self.player.x, self.player.y
        
        half_scale = self.player.scale/2

        if player_x - half_scale < -half_width:
            self.player.x = -half_width + half_scale
            self.player.x_velocity = 0
        elif player_x + half_scale > half_width:
            self.player.x = half_width - half_scale
            self.player.x_velocity = 0

        # Check for vertical bounds
        if player_y - half_scale < -half_height:
            self.player.y = -half_height + half_scale
            self.player.y_velocity = 0
        elif player_y + half_scale > half_height:
            self.player.y = half_height - half_scale
            self.player.y_velocity = 0

    def handle_player_projectile_collisions(self):
        if not np.count_nonzero(self.enemies.used_mask):
            return
        if not np.count_nonzero(self.player_projectiles.used_mask):
            return
    
        subset = self.enemies.data[self.enemies.used_mask, :4]
        collisions = self.player_projectiles.check_collisions_multiple(
            subset[:, :2],
            subset[:, 3]
        )

        indices = [i for i, j in enumerate(self.enemies.used_mask) if self.enemies.used_mask[i]]
        for i, id_ in enumerate(indices):
            cols = collisions[i]
            if not cols:
                continue
            if self.enemies.data[id_, 19] > 0:
                self.enemies.data[id_, 19] = max(0, self.enemies.data[id_, 19] - 5 * len(cols))
            else:
                self.enemies.data[id_, 18] = max(0, self.enemies.data[id_, 18] - 5 * len(cols))

            if self.enemies.data[id_, 18] <= 0:
                self.enemies.despawn(id_)
        to_despawn = list(set(proj for collision in collisions for proj in collision))
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
        # Update sliders
        if self.show_sliders:
            self.player.base_acceleration = self.sliders["base_acceleration"].value
            self.player.max_velocity = self.sliders["max_velocity"].value
            self.player.min_velocity = self.sliders["min_velocity"].value
            self.player.decay_rate = self.sliders["decay_rate"].value
            self.player.fire_rate = self.sliders["fire_rate"].value
            self.player.projectile_decay_rate = self.sliders["projectile_decay_rate"].value
            self.player.projectile_speed_multiplier = self.sliders["projectile_speed_multiplier"].value
            self.player.range = self.sliders["range"].value
            self.gravity = self.sliders["gravity"].value
            # Update slider text
            for name, slider in self.sliders.items():
                slider.text = f"{name}: {slider.value:.2f}"
        if self.show_info:
            self.update_info_display()

    def handle_portal_collisions(self):
        now = time.time()
        if self.player.next_portal < now:
            cols = self.portal_manager.check_collisions(self.player.position2d, self.player.scale/3, overlap=1)
            if len(cols):
                _id = cols[0]
                ids = self.portal_manager.get_paired_indicies(cols[0])
                _id2 = [__id for __id in ids if not __id == _id][0]
                pos = self.portal_manager.data[_id2][0:2]
                self.player.x, self.player.y = (*pos[0:2],)
                self.player.next_portal = now + self.player.portal_cooldown 

    def handle_portal_collisions_abstract(self, entity_system):
        """Handles portal collisions for all entities in the system."""
        now = time.time()-self.start
        
        eligible_entities = np.where(entity_system.data[:, 12] < now)[0]
        if not len(eligible_entities):
            return
        subset_positions = entity_system.data[:, 0:2][eligible_entities]
        subset_scales = entity_system.data[:, 2][eligible_entities]
        collisions = self.portal_manager.check_collisions_multiple(
            subset_positions,
            subset_scales
        )
        for i, id_ in enumerate(eligible_entities):
            if not len(collisions[i]):
                continue
            primary_portal = collisions[i][0]
            paired_portals = self.portal_manager.get_paired_indicies(primary_portal)
            paired_portal = [p for p in paired_portals if p != primary_portal][0]
            target_position = self.portal_manager.data[paired_portal][0:2]
            entity_system.data[id_, 0:2] = target_position
            entity_system.data[id_, 12] = now + 0.5
        
    def update(self):
        if not all((self.game_running, not self.paused)):
            return
        # self.profiler_data = {}
        start_time = time.perf_counter()

        dt = ursina.time.dt

        start_time = time.perf_counter()
        self.player.handle_movement(dt)
        self.record_time('Player Movement', start_time)

        start_time = time.perf_counter()
        self.player.handle_projectile()
        self.record_time('Player Projectile', start_time)

        start_time = time.perf_counter()
        self.handle_player_bounds()
        self.record_time('Player Bounds', start_time)

        start_time = time.perf_counter()
        self.player_projectiles.update(dt)
        self.record_time('Player Projectiles Update', start_time)

        start_time = time.perf_counter()
        self.enemies.update(dt)
        self.record_time('Enemies Update', start_time)

        start_time = time.perf_counter()
        self.enemies.resolve_external_overlap(self.player.position2d, self.player.scale)
        self.record_time('Enemies Overlap Resolve', start_time)

        start_time = time.perf_counter()
        self.enemy_projectiles.update(dt)
        self.record_time('Enemy Projectiles Update', start_time)

        start_time = time.perf_counter()
        self.handle_player_projectile_collisions()
        self.record_time('Player Projectile Collisions', start_time)

        start_time = time.perf_counter()
        self.handle_enemy_projectile_collisions()
        self.record_time('Enemy Projectile Collisions', start_time)

        start_time = time.perf_counter()
        self.handle_portal_collisions()
        self.record_time('Portal Collisions', start_time)

        start_time = time.perf_counter()
        self.handle_portal_collisions_abstract(self.player_projectiles)
        self.record_time('Projectile Portal Collisions', start_time)

        start_time = time.perf_counter()
        self.handle_portal_collisions_abstract(self.enemies)
        self.record_time('Enemy Portal Collisions', start_time)

        start_time = time.perf_counter()
        self.handle_portal_collisions_abstract(self.enemy_projectiles)
        self.record_time('Enemy Projectile Portal Collisions', start_time)

        # write shader data
        self.player.update_ssbo()
        self.layers["canvas"].set_shader_input("PlayerData", self.player.ssbo)
        self.layers["canvas"].set_shader_input("enemy_count", np.count_nonzero(self.enemies.used_mask))
        self.layers["canvas"].set_shader_input("EnemyData", self.enemies.ssbo)
        self.layers["canvas"].set_shader_input("EnemyProjectileData", self.enemy_projectiles.ssbo)
        self.layers["canvas"].set_shader_input("enemy_projectile_count", np.count_nonzero(self.enemy_projectiles.used_mask))
        self.layers["canvas"].set_shader_input("PlayerProjectileData", self.player_projectiles.ssbo)
        self.layers["canvas"].set_shader_input("player_projectile_count", np.count_nonzero(self.player_projectiles.used_mask))

        if not self.tick % 60:
            self.update_ui()

        self.tick += 1
        
    def record_time(self, label, start_time):
        elapsed_time = (time.perf_counter() - start_time) * 1000
        self.profiler_data[label] = elapsed_time

    def update_info_display(self):
        prof = self.profiler_data.copy()
        prof.update(self.enemies.profiler_data)
        player = {
            "X" :                       self.player.x,
            "Y" :                       self.player.y,
            "X Vel":                    self.player.x_velocity,
            "Y Vel":                    self.player.y_velocity,
            "Total Vel":                self.player.total_velocity,
            "Projectile Count":         np.count_nonzero(self.player_projectiles.used_mask),
            "Enemy Count":              np.count_nonzero(self.enemies.used_mask),
            "Enemy Projectile Count":   np.count_nonzero(self.enemy_projectiles.used_mask),
        }
        player_text = "Player Info:\n" + "\n".join(
            [f"{key}: {value:.2f}" for key, value in player.items()]
        )
        profiler_text = "Profiler Data (ms):\n" + "\n".join(
            [f"{key}: {value:.2f}" for key, value in prof.items()]
        )
        self.info_display.text = player_text + "\n\n" + profiler_text

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

ursina.window.vsync = False
game = Game()
update = game.update
ursina.window.exit_button.enabled = True
ursina.window.center_on_screen()
ursina.camera.orthographic = True
ursina.camera.fov = 10
game.app.run()