import time
import numpy as np
import ursina
from panda3d.core import GeomEnums, ShaderBuffer
import ursina.vec2

class _PhysicsEntity:
    """Abstract Physics Entity, do not instantiate directly"""
    __slots__ = ["manager", "_id"]
    def __init__(self, manager, _id:int):
        self.manager = manager
        self._id = _id # Don't override default `id` field
    
    def despawn(self) -> None:
        self.manager.despawn(self._id)


class _BaseEnemy(_PhysicsEntity):
    # Data for .spawn() instantiation only,
    # do not use these values in methods
    _max_health = 20
    _max_shield = 20
    _awareness_range=0
    _max_follow_range=0
    _movement_decay=1
    _max_velocity=0,
    _attack_cooldown=2.0
    _projectile_decay=1
    _color=ursina.color.orange
    _scale=1
    _projectile_color=ursina.color.red
    _projectile_range=0
    _projectile_speed=0
    _projectile_scale=1

    def __init__(self, manager, name:str, _id:int):
        _PhysicsEntity.__init__(self, manager, _id)
        self.name = name
        
    def update(self):
        pass


class FloatingFollower(_BaseEnemy):
    """
    Floating enemy that follows player when in range
    """
    # _awareness_range=5*6
    # _max_follow_range=7.5*6
    _awareness_range=10*6
    _max_follow_range=7.5*6
    _movement_decay=0.6
    _max_velocity=10
    _base_acc=18
    _attack_cooldown=1.1
    _color=ursina.color.orange
    _projectile_decay=0.005
    _projectile_color=ursina.color.red
    _projectile_range=1.75
    _projectile_scale=1.75
    _projectile_speed=13
    _scale=3

    def __init__(self, manager, _id:int):
        _PhysicsEntity.__init__(self, manager, _id)
        self.name = f"FloatingFollower_{_id}"
        
    def update(self):
        pass


class EnemyManager:
    def __init__(self, game, max_entities: int = 255, arena_size:ursina.Vec2 = ursina.Vec2(23,13)):
        self.game = game
        self.bounds = arena_size
        self.max_entities = max_entities
        self.entities = {}
        self.open_indicies = list(range(max_entities))
        self.used_indicies = []
        # Used to index enemy types for the renderer
        self.types = [FloatingFollower]

        self.data = np.zeros((max_entities, 33), dtype=np.float32)
        self._buffer = np.zeros((max_entities, 12), dtype=np.float32)

        ### THESE 8 COLUMNS ARE ALIGNED FOR BUFFER
        # positions  =   [:, 0:2  ] .data & ._buffer
        # scales     =   [:, 2:3  ] .data & ._buffer
        # types      =   [:, 3:4  ] .data & ._buffer
        # colors     =   [:, 4:8  ] .data & ._buffer
        
        ### ONLY IN DATA
        # velocities =   [:, 8:10 ] .data
        # acceleration=  [:, 10:12] .data
        # max_velocity=  [:, 12:13] .data
        # base_acc   =   [:, 13:14] .data
        # decays     =   [:, 14:15] .data
        # spawns     =   [:, 15:16] .data

        # THESE 4 MAKE UP THE LAST 4 BYTES SENT TO SHADER
        # max_health =   [:, 16:17] .data
        # max_shield =   [:, 17:18] .data
        # health     =   [:, 18:19] .data
        # shield     =   [:, 19:20] .data

        ### ONLY IN DATA
        # awareness  =   [:, 20:21] .data
        # follow_rng =   [:, 21:22] .data
        # p_cooldown =   [:, 22:23] .data
        # p_nexttime =   [:, 23:24] .data
        # proj_range =   [:, 24:25] .data
        # proj_scale =   [:, 25:26] .data
        # proj_decay =   [:, 26:27] .data
        # proj_color =   [:, 27:31] .data
        # proj_speed =   [:, 31:32] .data
        # detected   =   [:, 32,33] .data

        self.ssbo = None  # Placeholder for Shader Buffer Object
        self.update_ssbo()

    def update_ssbo(self):
        self._buffer[:len(self.used_indicies), 0:8]  = self.data[:, 0:8][self.used_indicies]
        self._buffer[:len(self.used_indicies), 8:12] = self.data[:, 16:20][self.used_indicies]
        self.ssbo = ShaderBuffer("drawableData", self._buffer.tobytes(), GeomEnums.UH_static)

    def resolve_overlaps(self):
        positions = self.data[:, 0:2][self.used_indicies]
        scales = self.data[:, 2:3][self.used_indicies]
        num_entities = len(self.used_indicies)
        if num_entities < 2: return  # No overlaps
        diffs = positions[:, None, :] - positions[None, :, :]
        dists = np.linalg.norm(diffs, axis=-1)
        min_distances = (scales + scales.T) / 2
        overlap_mask = (dists < min_distances) & (dists > 0)
        overlap_amounts = np.where(overlap_mask, min_distances - dists, 0)
        directions = np.divide(diffs, dists[..., None] + 1e-4, where=(dists[..., None] > 1e-4))  
        corrections = overlap_amounts[..., None] * directions / 6
        position_corrections = np.nansum(corrections, axis=1) - np.nansum(corrections, axis=0)
        self.data[:, 0:2][self.used_indicies] += position_corrections

    def resolve_external_overlap(self, position, scale):
        positions = self.data[:, 0:2][self.used_indicies]
        scales = self.data[:, 2:3][self.used_indicies].flatten()
        diffs = positions - position
        dists = np.linalg.norm(diffs, axis=-1)
        min_distances = (scales + scale) / 2
        overlap_mask = (dists < min_distances) & (dists > 0)
        overlap_amounts = np.where(overlap_mask, min_distances - dists, 0)
        directions = np.divide(diffs, dists[:, None] + 1e-4, where=(dists[:, None] > 1e-4))
        corrections = overlap_amounts[:, None] * directions / 3.5 
        self.data[:, 0:2][self.used_indicies] += corrections

    def update(self):
        # Calculate in-range enemies and set aggro
        player = self.game.player
        data_subset = self.data[self.used_indicies]
        subset_indices = np.where(self.used_indicies)[0]
        dx = player.x - data_subset[:, 0]
        dy = player.y - data_subset[:, 1]
        distance = np.sqrt(dx**2 + dy**2)
        rng = np.where(data_subset[:, 32].astype(bool), data_subset[:, 21], data_subset[:, 20])
        valid_subset_indices = np.where(distance <= (player.scale[0] / 3 + rng / 2))[0]
        valid_indices = [self.used_indicies[i] for i in subset_indices[valid_subset_indices]]
        invalid_indices = [i for i in self.used_indicies if not i in valid_indices]
        self.data[:, 32][invalid_indices] = 0.0 # Remove aggro flag
        self.data[:, 32][valid_indices] = 1.0 # Set aggro flag
        # Apply acceleration to in-range enemies
        dx = player.x - self.data[:, 0][valid_indices]
        dy = player.y - self.data[:, 1][valid_indices]
        angles = np.arctan2(dx, dy)
        x_accels = np.sin(angles) 
        y_accels = np.cos(angles)
        # Set accel vector
        self.data[:, 10][valid_indices] = x_accels * self.data[:, 13][valid_indices]
        self.data[:, 11][valid_indices] = y_accels * self.data[:, 13][valid_indices]
        # Apply acceleration to velocity
        self.data[:, 8:10][self.used_indicies] = (
            self.data[:, 8:10][self.used_indicies]
            + self.data[:, 10:12][self.used_indicies] * ursina.time.dt
        )
        # Apply speed decay
        self.data[:, 8:10][self.used_indicies] = (
            self.data[:, 8:10][self.used_indicies]
            * (1-(self.data[:, 14:15][self.used_indicies] * ursina.time.dt))
        )
        # Handle overlaps
        self.resolve_overlaps()
        # Handle wall colisions
        half_width, half_height = self.bounds[0] * 1.5, self.bounds[1] * 1.5
        positions = self.data[:, 0:2]
        velocities = self.data[:, 8:10]
        scales = self.data[:, 2:3]
        half_scales = scales / 2
        min_bounds = -np.array([half_width, half_height]) + half_scales
        max_bounds = np.array([half_width, half_height]) - half_scales
        too_low = positions < min_bounds
        positions[too_low] = min_bounds[too_low]
        velocities[too_low] = 0
        too_high = positions > max_bounds
        positions[too_high] = max_bounds[too_high]
        velocities[too_high] = 0
        self.data[:, 0:2] = positions
        self.data[:, 8:10] = velocities
        # Apply velocities
        self.data[:, 0:2][self.used_indicies] = (
            self.data[:, 0:2][self.used_indicies]
            + (self.data[:, 8:10][self.used_indicies]
            * ursina.time.dt)
        )
        now = np.float32(time.time() - self.game.start)
        fire_times = self.data[:, 23:24][self.used_indicies]
        subset_indices = np.where(self.used_indicies)[0]
        to_fire = np.where(fire_times < now)[0] 
        valid_fire_conditions = self.data[:, 32][self.used_indicies] == 1.0
        to_fire = [self.used_indicies[i] for i in subset_indices[to_fire] if valid_fire_conditions[i]]
        if len(to_fire): 
            self.handle_spawning_projectiles(to_fire)
        self.update_ssbo()

    def spawn(
        self,
        type_=FloatingFollower,
        position:ursina.Vec2 = ursina.Vec2(0),
        velocity:ursina.Vec2 = ursina.Vec2(0),
        acceleration:ursina.Vec2 = ursina.Vec2(0),
    ):
        """Returns spawned object, or None if spawn failed"""
        if not self.open_indicies: return
        if not type_ in self.types:
            raise ValueError("Tried to spawn unindexed entity")
        id_ = self.open_indicies.pop()
        self.used_indicies.append(id_)
        proj = type_(self, id_)
        now = np.float32(time.time() - self.game.start)
        # Write data to numpy array
        self.data[id_] = (
            *(position * 3),
            type_._scale,
            self.types.index(type_),
            *type_._color,
            *velocity,
            *acceleration,
            type_._max_velocity,
            type_._base_acc,
            type_._movement_decay,
            now,
            type_._max_health,
            type_._max_shield,
            type_._max_health,
            type_._max_shield,
            type_._awareness_range,
            type_._max_follow_range,
            type_._attack_cooldown,
            now + type_._attack_cooldown,
            type_._projectile_range,
            type_._projectile_scale,
            type_._projectile_decay,
            *type_._projectile_color,
            type_._projectile_speed,
            0
        )
        self.entities[id_] = proj
        return proj

    def despawn(self, id_:int) -> bool:
        """Return a bool indicating if the index was in use"""
        if not id_ in self.used_indicies:
            return False
        self.entities.pop(id_)
        self.used_indicies.remove(id_)
        self.open_indicies.append(id_)

    def despawn_multiple(self, ids:list) -> None:
        for id_ in ids:
            self.entities.pop(id_)
            self.used_indicies.remove(id_)
        self.open_indicies.extend(ids)

    def handle_spawning_projectiles(self, ids:list, target=None) -> None:
        buffer = np.zeros((len(ids), 12), dtype=np.float32)
        now = np.float32(time.time() - self.game.start)
        # set positions
        buffer[:, 0:2] = self.data[:, 0:2][ids] # position
        buffer[:, 2:3] = self.data[:, 25:26][ids]
        buffer[:, 3:4] = now
        buffer[:, 4:8] = self.data[:, 27:31][ids]
        target = target or self.game.player
        # calc velocities
        dx = target.x - self.data[:, 0][ids]
        dy = target.y - self.data[:, 1][ids]
        angles = np.arctan2(dx, dy)
        buffer[:, 8] = 2 * np.sin(angles) * self.data[:, 31][ids] + self.data[:, 8][ids] * 1/288
        buffer[:, 9] = 2 * np.cos(angles) * self.data[:, 31][ids] + self.data[:, 9][ids] * 1/288
        # set range, scale, decay, and color
        buffer[:, 10:11] = self.data[:, 24:25][ids]
        buffer[:, 11:12] = self.data[:, 26:27][ids]
        # set next fire time
        self.data[:, 23:24][ids] = now + self.data[:, 22:23][ids]
        self.game.enemy_projectiles.spawn_bulk(buffer)