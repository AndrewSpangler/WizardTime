import time
import ursina
import numpy as np
from panda3d.core import ShaderBuffer, GeomEnums

class ProjectileManager:
    def __init__(self, game, name:str, max_entities: int = 255, arena_size: ursina.Vec2 = ursina.Vec2(23, 13)):
        self.game = game
        self.name = name
        self.bounds = arena_size
        self.half_width, self.half_height = self.bounds[0] / 2, self.bounds[1] / 2
        self.max_entities = max_entities
        self.entities = {}
        self.open_indicies = list(range(max_entities))
        self.used_mask = np.zeros(max_entities, dtype=bool)
        self.data = np.zeros((max_entities, 13), dtype=np.float32)
        self._buffer = np.zeros((max_entities, 8), dtype=np.float32)
        self.ssbo = None
        self.update_ssbo()

    def update_ssbo(self):
        active_data = self.data[self.used_mask]
        self._buffer[:len(active_data)] = active_data[:, :8]
        self.ssbo = ShaderBuffer(f"{self.name}ProjectileData", self._buffer.tobytes(), GeomEnums.UH_static)

    def update(self, dt):
        if not np.any(self.used_mask):
            return

        mask = self.used_mask
        half_width, half_height = self.half_width, self.half_height
        self.data[mask, 8:10] *= 1 - self.data[mask, 11][:, np.newaxis]
        self.data[mask, 0:2] += self.data[mask, 8:10] * ursina.time.dt

        out_of_bounds_mask = (np.abs(self.data[mask, 0]) > half_width * 3) | (np.abs(self.data[mask, 1]) > half_height * 3)
        to_despawn_out_of_bounds = np.where(out_of_bounds_mask)[0]
        if to_despawn_out_of_bounds.size:
            self.despawn_multiple(to_despawn_out_of_bounds)

        time_elapsed = time.time() - self.game.start
        expired_mask = (self.data[:, 3] + self.data[:, 10] < time_elapsed)
        to_despawn_expired = np.where(expired_mask)[0]
        if to_despawn_expired.size:
            self.despawn_multiple(to_despawn_expired)

        self.update_ssbo()

    def spawn(self, position: ursina.Vec2 = ursina.Vec2(0),
              velocity: ursina.Vec2 = ursina.Vec2(0),
              _range: float = 3,
              scale: float = 1.75,
              decay: float = 0.01,
              color: ursina.Vec4 = ursina.Vec4(0, 0, 1, 1)) -> int | None:
        if not np.any(~self.used_mask):
            return None
        _id = np.argmax(~self.used_mask)
        self.used_mask[_id] = True

        now = time.time() - self.game.start
        self.data[_id] = (*position, scale, now, *color, *velocity, _range, decay, now)
        return _id

    def spawn_bulk(self, buffer: np.ndarray) -> None:
        available_slots = np.where(~self.used_mask)[0]
        buflen = len(buffer)
        if len(available_slots) < buflen:
            return print("Spawning too many entities")

        self.used_mask[available_slots[:buflen]] = True
        self.data[available_slots[:buflen]] = buffer

    def despawn(self, _id: int) -> bool:
        if self.used_mask[_id]:
            self.used_mask[_id] = False
            return True
        return False

    def despawn_multiple(self, ids: list) -> None:
        if len(ids):
            self.used_mask[ids] = False

    def check_collisions(self, position: ursina.vec2, scale: float) -> list[int]:
        if not np.any(self.used_mask):
            return []

        used_indices = np.where(self.used_mask)[0]
        subset_data = self.data[self.used_mask]
        dx, dy = subset_data[:, 0] - position[0], subset_data[:, 1] - position[1]
        dist_squared = dx**2 + dy**2
        collision_dist_squared = ((scale / 2) + subset_data[:, 2])**2
        collision_mask = dist_squared <= collision_dist_squared
        return used_indices[collision_mask].tolist()


    def check_collisions_multiple(self, positions: np.ndarray, scales: np.ndarray) -> list[list[int]]:
        if not np.any(self.used_mask):
            return [[] for _ in range(len(positions))]

        subset_data = self.data[self.used_mask]
        subset_positions = subset_data[:, :2]
        subset_radii = subset_data[:, 2]

        pos_diff = subset_positions - positions[:, np.newaxis, :]
        dist_squared = np.sum(pos_diff ** 2, axis=-1)
        collision_dist_squared = ((scales[:, np.newaxis] / 2) + subset_radii[np.newaxis, :]) ** 2

        collision_mask = dist_squared <= collision_dist_squared
        collision_indices = [np.where(mask)[0].tolist() for mask in collision_mask]
    
        return collision_indices
