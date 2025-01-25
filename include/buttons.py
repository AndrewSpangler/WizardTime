import time
import ursina
import numpy as np
from panda3d.core import ShaderBuffer, GeomEnums

class ButtonManager:
    def __init__(self, game, name:str, max_entities: int = 32):
        self.game = game
        self.name = name
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
            return self.update_ssbo()
        self.update_ssbo()

    def check_collisions(self, position: ursina.vec2, scale: float) -> list[int]:
        if not np.any(self.used_mask):
            return []

        # Extract indices of used elements
        used_indices = np.where(self.used_mask)[0]
        
        # Subset the data based on the mask
        subset_data = self.data[self.used_mask]

        # Calculate distances
        dx, dy = subset_data[:, 0] - position[0], subset_data[:, 1] - position[1]
        dist_squared = dx**2 + dy**2
        collision_dist_squared = ((scale / 2) + subset_data[:, 2])**2

        # Create the collision mask
        collision_mask = dist_squared <= collision_dist_squared

        # Map subset indices back to full indices
        return used_indices[collision_mask].tolist()