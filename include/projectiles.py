import time
import ursina
import numpy as np
from panda3d.core import ShaderBuffer, GeomEnums

### PROJECTILES
class ProjectileManager:
    def __init__(self, game, max_entities: int = 255, arena_size:ursina.Vec2 = ursina.Vec2(23,13)):
        self.game = game
        self.bounds = arena_size
        self.half_width = self.bounds[0] / 2 # pre-calc for bbox check
        self.half_height = self.bounds[1] / 2 # pre-calc for bbox check
        self.max_entities = max_entities
        self.entities = {}
        self.open_indicies = list(range(max_entities))
        self.used_indicies = []
        self.data = np.zeros((max_entities, 12), dtype=np.float32)
        # Basically a chunk of ram to buffer for the shader
        self._buffer = np.zeros((max_entities, 8), dtype=np.float32)
        ### THESE 8 COLUMNS ARE ALIGNED FOR SHADER
        # positions  =   [:, 0:2  ] .data & ._buffer
        # scales     =   [:, 2:3  ] .data & ._buffer
        # spawns     =   [:, 3:4  ] .data & ._buffer
        # colors     =   [:, 4:8  ] .data & ._buffer
        ### ONLY IN DATA
        # velocities =   [:, 8:10 ] .data
        # ranges     =   [:, 10:11] .data
        # decays     =   [:, 11:12] .data
        self.ssbo = None  # Placeholder for Shader Buffer Object
        self.update_ssbo()

    def update_ssbo(self):
        # move new data to beginning of buffer
        self._buffer[:len(self.used_indicies)] = self.data[:, 0:8][self.used_indicies]
        self.ssbo = ShaderBuffer("projectileData", self._buffer.tobytes(), GeomEnums.UH_static)

    def update(self):
        # Apply speed decay
        self.data[:, 8:10][self.used_indicies] = (
            self.data[:, 8:10][self.used_indicies]
            * (1-self.data[:, 11:12][self.used_indicies])
        )

        # Update position
        self.data[:, 0:2][self.used_indicies] = (
            self.data[:, 0:2][self.used_indicies]
            + self.data[:, 8:10][self.used_indicies]
            * ursina.time.dt
        )
        now = time.time()-self.game.start

        # Despawn projectiles that hit the walls
        half_width, half_height = self.bounds[0] / 2, self.bounds[1] / 2
        mask = (
            (abs(self.data[self.used_indicies, 0]) > half_width * 3) |
            (abs(self.data[self.used_indicies, 1]) > half_height * 3)
        )
        to_despawn = np.array(self.used_indicies)[mask]
        if len(to_despawn):
            self.despawn_multiple(to_despawn)

        # Despawn projectiles at end of range
        to_despawn = np.where(self.data[:, 3:4] + self.data[:, 10:11] < now)[0]
        to_despawn = [p for p in to_despawn if p in self.used_indicies]
        if len(to_despawn): self.despawn_multiple(set(to_despawn))

        self.update_ssbo()

    def spawn(
        self,
        position:ursina.Vec2 = ursina.Vec2(0),
        velocity:ursina.Vec2 = ursina.Vec2(0),
        _range:float = 3,
        scale:float = 1.75,
        decay:float = 0.01,
        color:ursina.Vec4 = ursina.Vec4(0,0,1,1)
    ) -> int | None:
        """Returns spawned object, or None if spawn failed"""
        if not self.open_indicies:
            return None
        _id = self.open_indicies.pop()
        self.used_indicies.append(_id)
        # Write data to numpy array
        self.data[_id] = (
            *position,
            scale,
            time.time()-self.game.start,
            *color,
            *velocity,
            _range,
            decay,          
        )
        return _id
    
    def spawn_bulk(self, buffer:np.ndarray) -> None:
        buflen = len(buffer)
        if len(self.open_indicies) < buflen:
            return print("Spawning too many entities")

        ids = self.open_indicies[:buflen]
        self.open_indicies = self.open_indicies[buflen:]
        self.data[:, :][ids] = buffer
        self.used_indicies.extend(ids)

    def despawn(self, _id:int) -> bool:
        """Return a bool indicating if the index was in use"""
        if not _id in self.used_indicies:
            return False
        self.used_indicies.remove(_id)
        self.open_indicies.append(_id)

    def despawn_multiple(self, ids:list) -> None:
        if not len(ids):
            return
        for _id in ids:
            if not _id in self.used_indicies:
                continue
            self.used_indicies.remove(_id)
            self.open_indicies.append(_id)

    def check_collisions(self, position:ursina.vec2, scale:tuple) -> list[int]:
        if not self.used_indicies: return []
        subset_data = self.data[self.used_indicies]
        dxy = subset_data[:, 0:2] - position
        dist_squared = dxy[:, 0]**2 + dxy[:, 1]**2
        collision_dist_squared = ((scale[0] / 2) + (subset_data[:, 2]))**2
        valid_subset_indices = np.where(dist_squared <= collision_dist_squared)[0]
        valid_indices = [self.used_indicies[i] for i in valid_subset_indices]
        return valid_indices