import numpy as np
import time
import ursina
from panda3d.core import ShaderBuffer, GeomEnums

class PortalManager:
    def __init__(self, game, max_portal_pairs:int=16):
        self.game = game
        self.max_portal_pairs = max_portal_pairs
        self.data = np.zeros((max_portal_pairs*2, 8), dtype=np.float32)
        self.open_indicies = list(range(max_portal_pairs))
        self.used_mask = np.zeros(max_portal_pairs, dtype=bool)
        self.ssbo = None
        self.update_ssbo()

    def update_ssbo(self):
        self.ssbo = ShaderBuffer("portalData", self.data.tobytes(), GeomEnums.UH_static)

    def add_portal_pair(self, position1:ursina.Vec2, scale1:float, color1:ursina.Vec4, position2:ursina.Vec2, scale2:float, color2:ursina.Vec4) -> int:
        if position1 == position2:
            raise ValueError("Portal pairs cannot overlap")
        if not self.open_indicies:
            raise ValueError("Cannot spawn more portals")
        
        id_ = np.argmax(~self.used_mask)
        if id_ == self.max_portal_pairs:
            raise ValueError("Cannot spawn more portals")
        self.used_mask[id_] = True
        now = np.float32(time.time() - self.game.start)
        self.data[id_] = (*position1, scale1/3, now, *color1)
        self.data[id_ + self.max_portal_pairs] = (*position2, scale2/3, now, *color2)
        return id_

    def get_paired_indicies(self, _id) -> tuple[int, int]:
        return (_id - self.max_portal_pairs, _id) if _id >= self.max_portal_pairs else (_id, _id + self.max_portal_pairs)

    def check_collisions(self, position: ursina.vec2, scale: float, overlap: float = 0) -> list[int]:
        if not np.any(self.used_mask):
            return []

        max_portal_pairs = self.max_portal_pairs
        masklist = np.where(self.used_mask)[0].tolist()
        combined_indices = np.array(masklist + [i + max_portal_pairs for i in masklist])
        combined_data = self.data[combined_indices]
        positions_combined = combined_data[:, :2]
        scales_combined = combined_data[:, 2]
        dxy = positions_combined - position
        dist_squared = np.sum(dxy**2, axis=1)
        collision_dist_squared = ((scale / 2) + scales_combined) ** 2 + overlap
        valid_indices = combined_indices[dist_squared <= collision_dist_squared]
        return valid_indices.tolist()

    def check_collisions_multiple(self, positions: list[ursina.vec2], scales: list[float]) -> list[list[int]]:
        if not np.any(self.used_mask):
            return [[] for _ in range(len(positions))]
        max_portal_pairs = self.max_portal_pairs
        masklist = np.where(self.used_mask)[0].tolist()
        combined_indicies = np.array(masklist + [i + max_portal_pairs for i in masklist])
        combined_data = self.data[combined_indicies]
        positions_combined = combined_data[:, :2]
        scales_combined = combined_data[:, 2]
        dist_squared = np.sum((positions_combined[:, np.newaxis, :] - np.array(positions)) ** 2, axis=2)
        collision_dist_squared = ((np.array(scales) / 2) + scales_combined[:, np.newaxis]) ** 2 + 1
        valid_indices = [combined_indicies[dist_squared[:, i] <= collision_dist_squared[:, i]] for i in range(len(positions))]
        return valid_indices

