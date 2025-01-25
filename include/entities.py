import time
import numpy as np
import ursina
from panda3d.core import GeomEnums, ShaderBuffer

class _PhysicsEntity:
    """Abstract Physics Entity, do not instantiate directly"""
    __slots__ = ["manager", "_id"]
    def __init__(self, manager, _id:int):
        self.manager = manager
        self._id = _id # Don't override default `id` field
    
    def despawn(self) -> None:
        self.manager.despawn(self._id)

class _BaseEnemy(_PhysicsEntity):
    # data for .spawn() instantiation only,
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
    _awareness_range=6*6
    _max_follow_range=10*6
    _movement_decay=0.7
    _max_velocity=10
    _base_acc=15
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
    def __init__(self, game, name:str, max_entities: int = 255, arena_size: ursina.Vec2 = ursina.Vec2(23, 13)):
        self.game = game
        self.name = name
        self.bounds = arena_size
        self.max_entities = max_entities
        self.entities = {}

        self.open_indicies = list(range(max_entities))
        self.used_mask = np.zeros(max_entities, dtype=bool)  # Boolean mask for used indices
        self.types = [FloatingFollower]

        self.data = np.zeros((max_entities, 33), dtype=np.float64)
        self._buffer = np.zeros((max_entities, 12), dtype=np.float32)

        self.profiler_data = {}
        self.ssbo = None
        self.update_ssbo()

    def update_ssbo(self):
        used_indices_len = np.count_nonzero(self.used_mask)
        self._buffer[:used_indices_len, 0:8] = self.data[self.used_mask, 0:8]
        self._buffer[:used_indices_len, 8:12] = self.data[self.used_mask, 16:20]
        self.ssbo = ShaderBuffer(f"{self.name}DrawableData", self._buffer.tobytes(), GeomEnums.UH_static)

    def update(self, dt: float):
        if not np.any(self.used_mask):
            return self.update_ssbo()

        player = self.game.player
        start_time0 = time.perf_counter()

        # get subset of data based on the used_mask
        used_data_subset = self.data[self.used_mask]
        self.record_time('ENEMIES - Filter Used', start_time0)

        start_time = time.perf_counter()
        dx = player.x - used_data_subset[:, 0]
        dy = player.y - used_data_subset[:, 1]
        distance = np.sqrt(dx**2 + dy**2)
        rng = np.where(used_data_subset[:, 32].astype(bool), used_data_subset[:, 21], used_data_subset[:, 20])
        valid_mask = distance <= (player.scale / 3 + rng / 2)
        self.record_time('ENEMIES - Filter Distances', start_time)

        # process out of range entities based on mask
        start_time = time.perf_counter()
        out_of_range_mask = ~valid_mask
        used_data_subset[out_of_range_mask, 32] = 0.0  
        used_data_subset[out_of_range_mask, 10:12] = (0, 0)
        self.record_time('ENEMIES - Reset Out-Ranges', start_time)

        # update entities within valid range
        start_time = time.perf_counter()
        if np.any(valid_mask):
            used_data_subset[valid_mask, 32] = 1.0
            valid_positions = used_data_subset[valid_mask, 0:2]
            dx, dy = player.x - valid_positions[:, 0], player.y - valid_positions[:, 1]
            angles = np.arctan2(dx, dy)
            accels = np.column_stack((np.sin(angles), np.cos(angles))) * used_data_subset[valid_mask, 13:14]
            used_data_subset[valid_mask, 10:12] = accels
            velocities = used_data_subset[valid_mask, 10:12] 
            used_data_subset[valid_mask, 8:10] += accels * ursina.time.dt
            self.data[self.used_mask] = used_data_subset
        self.record_time('ENEMIES - Set In-Ranges', start_time)

        self.data[self.used_mask, 9] -= self.game.gravity

        start_time = time.perf_counter()
        self.resolve_overlaps()
        self.record_time('ENEMIES - Resolve Overlaps', start_time)

        # apply movement
        start_time = time.perf_counter()
        self.data[self.used_mask, 8:10] *= (1 - self.data[self.used_mask, 14:15] * ursina.time.dt)

        half_scales = self.data[:, 2:3][self.used_mask] / 2
        min_bounds = -np.array(self.bounds) * 1.5 + half_scales
        max_bounds = np.array(self.bounds) * 1.5 - half_scales
        positions = self.data[:, 0:2][self.used_mask]
        velocities = self.data[:, 8:10][self.used_mask]

        too_low = positions < min_bounds
        positions[too_low], velocities[too_low] = min_bounds[too_low], 0
        too_high = positions > max_bounds
        positions[too_high], velocities[too_high] = max_bounds[too_high], 0

        self.data[self.used_mask, 0:2], self.data[self.used_mask, 8:10] = positions, velocities
        self.data[self.used_mask, 0:2] += self.data[self.used_mask, 8:10] * ursina.time.dt
        self.record_time('ENEMIES - Apply Movement', start_time)

        # get aggrod
        start_time = time.perf_counter()
        now = np.float32(time.time() - self.game.start)
        fire_times = used_data_subset[:, 23:24]
        to_fire_mask = (fire_times.flatten() < now) & (used_data_subset[:, 32] == 1.0)

        self.record_time('ENEMIES - Handle Fire Times', start_time)
        used_data_subset = self.data[self.used_mask]
        start_time = time.perf_counter()

        # spawn projectiles 
        if (count := np.count_nonzero(to_fire_mask)):
            to_fire = np.where(to_fire_mask)[0]
            buffer = np.zeros((count, 13), dtype=np.float32)

            buffer[:, 0:2] = used_data_subset[:, 0:2][to_fire]
            buffer[:, 2:3] = used_data_subset[:, 25:26][to_fire]
            buffer[:, 3:4] = now
            buffer[:, 4:8] = used_data_subset[:, 27:31][to_fire]

            dx = player.x - used_data_subset[:, 0][to_fire]
            dy = player.y - used_data_subset[:, 1][to_fire]
            angles = np.arctan2(dx, dy)

            buffer[:, 8] = 2 * np.sin(angles) * used_data_subset[:, 31][to_fire] + used_data_subset[:, 8][to_fire] / 288
            buffer[:, 9] = 2 * np.cos(angles) * used_data_subset[:, 31][to_fire] + used_data_subset[:, 9][to_fire] / 288
            buffer[:, 10:11] = used_data_subset[:, 24:25][to_fire]
            buffer[:, 11:12] = used_data_subset[:, 26:27][to_fire]
            buffer[:, 12:13] = now

            # update fire times
            used_data_subset[:, 23:24][to_fire] = now + used_data_subset[:, 22:23][to_fire]
            self.game.enemy_projectiles.spawn_bulk(buffer)
            
        self.data[self.used_mask, :] = used_data_subset
        self.record_time('ENEMIES - Handle Fire', start_time)

        self.update_ssbo()
        self.record_time('ENEMIES - Full Update', start_time0)

    def resolve_overlaps(self):
        num_entities = np.count_nonzero(self.used_mask)
        if num_entities < 2:
            return
        positions = self.data[self.used_mask, 0:2]
        scales = self.data[self.used_mask, 2:3]
        
        min_distances = (scales + scales.T) / 2
        diffs = positions[:, None] - positions[None, :]
        dists = np.linalg.norm(diffs, axis=-1)
        overlap_mask = (dists < min_distances) & ~np.eye(num_entities, dtype=bool)
        overlap_amounts = np.maximum(min_distances - dists, 0) * overlap_mask
        directions = diffs / (dists[..., None] + 1e-4)
        overlap_amounts_directions = overlap_amounts[..., None] * directions
        corrections = np.sum(overlap_amounts_directions, axis=1) - np.sum(overlap_amounts_directions, axis=0)
        corrections *= 12 * ursina.time.dt
        overlap_amounts_sum = np.sum(overlap_amounts)
        if overlap_amounts_sum > 0:
            correction_scale = overlap_amounts_sum / np.sum(overlap_amounts[overlap_amounts > 0])
            corrections *= correction_scale
        self.data[self.used_mask, 0:2] += corrections

    def resolve_external_overlap(self, position, scale):
        positions = self.data[self.used_mask, 0:2]
        scales = self.data[self.used_mask, 2:3].flatten()
        diffs = positions - position
        dists = np.linalg.norm(diffs, axis=-1)
        min_distances = (scales + scale) / 1.5
        overlap_mask = (dists < min_distances) & (dists > 0)
        overlap_amounts = np.maximum(min_distances - dists, 0) * overlap_mask
        directions = diffs / (dists[:, None] + 1e-4)
        corrections = overlap_amounts[:, None] * directions / 2
        self.data[self.used_mask, 0:2] += corrections

    def record_time(self, label, start_time):
        elapsed_time = (time.perf_counter() - start_time) * 1000
        self.profiler_data[label] = elapsed_time

    def spawn(self, type_=FloatingFollower, position: ursina.Vec2 = ursina.Vec2(0), velocity: ursina.Vec2 = ursina.Vec2(0), acceleration: ursina.Vec2 = ursina.Vec2(0)):
        if not self.open_indicies: return
        if type_ not in self.types:
            raise ValueError("Tried to spawn unindexed entity")
        id_ = self.open_indicies.pop()
        self.used_mask[id_] = True  # Set the mask for the new entity
        ent = type_(self, id_)
        now = np.float32(time.time() - self.game.start)
        self.data[id_] = (
            *(position * 3),
            type_._scale,
            self.types.index(type_),
            *type_._color,
            *velocity,
            *acceleration,
            now,
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
            0,
        )
        self.entities[id_] = ent
        return ent

    def despawn(self, id_: int) -> bool:
        if not self.used_mask[id_]:
            return False
        self.entities.pop(id_)
        self.used_mask[id_] = False
        self.open_indicies.append(id_)

    def despawn_multiple(self, ids: list) -> None:
        for id_ in ids:
            self.entities.pop(id_)
            self.used_indicies.remove(id_)
        self.open_indicies.extend(ids)