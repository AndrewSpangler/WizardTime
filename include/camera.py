"""Taken from ursina, modified for top-down 2D game"""

import ursina

class PlayerCamera(ursina.Entity):
    def __init__(self, **kwargs):
        ursina.camera.editor_position = ursina.camera.position
        super().__init__(name='player_camera', eternal=False, collider=None)

        self.rotation_speed = 200
        self.pan_speed = ursina.Vec2(5, 5)
        self.move_speed = 10
        self.target_fov = ursina.camera.fov
        self.zoom_speed = 1.25
        self.zoom_smoothing = 8
        self.rotate_around_mouse_hit = False
        self.ignore_scroll_on_ui = True

        self.smoothing_helper = ursina.Entity(add_to_scene_entities=False, collider=None)
        self.rotation_smoothing = 0
        self.look_at = self.smoothing_helper.look_at
        self.look_at_2d = self.smoothing_helper.look_at_2d
        self.rotate_key = 'right mouse'

        for key, value in kwargs.items():
            setattr(self, key, value)

        self.start_position = self.position
        self.perspective_fov = ursina.camera.fov
        self.orthographic_fov = ursina.camera.fov
        self.on_destroy = self.on_disable
        self.shortcuts = {'toggle_orthographic':'shift+p', 'focus':'shift+f', 'reset_center':'alt+f'}


    def on_enable(self):
        self.org_cam_par = ursina.camera.parent
        self.org_cam_pos = ursina.camera.position
        self.org_cam_rot = ursina.camera.rotation
        ursina.camera.parent = self
        ursina.camera.position = ursina.camera.editor_position
        ursina.camera.rotation = (0,0,0)
        self.target_z = ursina.camera.z
        self.target_fov = ursina.camera.fov


    def on_disable(self):
        ursina.camera.editor_position = ursina.camera.position

        # if we instantiate with enabled=False, this will get called before on_enable and these variables won't exist.
        if hasattr(self, 'org_cam_par'):
            ursina.camera.parent = self.org_cam_par
            ursina.camera.position = self.org_cam_pos
            ursina.camera.rotation = self.org_cam_rot


    def on_destroy(self):
        ursina.destroy(self.smoothing_helper)


    def input(self, key):
        return
        # combined_key = ''.join(e+'+' for e in ('control', 'shift', 'alt') if ursina.held_keys[e] and not e == key) + key

        # if combined_key == self.shortcuts['toggle_orthographic']:
        #     if not ursina.camera.orthographic:
        #         self.orthographic_fov = ursina.camera.fov
        #         ursina.camera.fov = self.perspective_fov
        #     else:
        #         self.perspective_fov = ursina.camera.fov
        #         ursina.camera.fov = self.orthographic_fov

        #     ursina.camera.orthographic = not ursina.camera.orthographic


        # elif combined_key == self.shortcuts['reset_center']:
        #     self.animate_position(self.start_position, duration=.1, curve=ursina.curve.linear)

        # elif combined_key == self.shortcuts['focus'] and ursina.mouse.world_point:
        #     self.animate_position(ursina.mouse.world_point, duration=.1, curve=ursina.curve.linear)


        # elif key == 'scroll up':
        #     if self.ignore_scroll_on_ui and ursina.mouse.hovered_entity and ursina.mouse.hovered_entity.has_ancestor(ursina.camera.ui):
        #         return
        #     if not ursina.camera.orthographic:
        #         target_position = self.world_position
        #         self.world_position = ursina.lerp(self.world_position, target_position, self.zoom_speed * time.dt * 10)
        #         self.target_z += self.zoom_speed * (abs(self.target_z)*.1)
        #     else:
        #         self.target_fov -= self.zoom_speed * (abs(self.target_fov)*.1)
        #         self.target_fov = ursina.clamp(self.target_fov, 1, 200)

        # elif key == 'scroll down':
        #     if self.ignore_scroll_on_ui and ursina.mouse.hovered_entity and ursina.mouse.hovered_entity.has_ancestor(ursina.camera.ui):
        #         return

        #     if not ursina.camera.orthographic:
        #         # camera.world_position += camera.back * self.zoom_speed * 100 * time.dt * (abs(camera.z)*.1)
        #         self.target_z -= self.zoom_speed * (abs(self.target_z)*.1)
        #     else:
        #         self.target_fov += self.zoom_speed * (abs(self.target_fov)*.1)
        #         self.target_fov = ursina.clamp(self.target_fov, 1, 200)

        # elif key == 'right mouse down' or key == 'middle mouse down':
        #     if ursina.mouse.hovered_entity and self.rotate_around_mouse_hit:
        #         org_pos = ursina.camera.world_position
        #         self.world_position = ursina.mouse.world_point
        #         ursina.camera.world_position = org_pos


    def update(self):
        # if ursina.held_keys['gamepad right stick y'] or ursina.held_keys['gamepad right stick x']:
        #     self.smoothing_helper.rotation_x -= ursina.held_keys['gamepad right stick y'] * self.rotation_speed / 100
        #     self.smoothing_helper.rotation_y += ursina.held_keys['gamepad right stick x'] * self.rotation_speed / 100

        # elif ursina.held_keys[self.rotate_key]:
        #     self.smoothing_helper.rotation_x -= ursina.mouse.velocity[1] * self.rotation_speed
        #     self.smoothing_helper.rotation_y += ursina.mouse.velocity[0] * self.rotation_speed

        #     self.direction = ursina.Vec3(
        #         self.forward * (ursina.held_keys['w'] - ursina.held_keys['s'])
        #         + self.right * (ursina.held_keys['d'] - ursina.held_keys['a'])
        #         + self.up    * (ursina.held_keys['e'] - ursina.held_keys['q'])
        #         ).normalized()

        #     self.position += self.direction * (self.move_speed + (self.move_speed * ursina.held_keys['shift']) - (self.move_speed*.9 * ursina.held_keys['alt'])) * time.dt

        #     if self.target_z < 0:
        #         self.target_z += ursina.held_keys['w'] * (self.move_speed + (self.move_speed * ursina.held_keys['shift']) - (self.move_speed*.9 * ursina.held_keys['alt'])) * time.dt
        #     else:
        #         self.position += ursina.camera.forward * ursina.held_keys['w'] * (self.move_speed + (self.move_speed * ursina.held_keys['shift']) - (self.move_speed*.9 * ursina.held_keys['alt'])) * time.dt

        #     self.target_z -= ursina.held_keys['s'] * (self.move_speed + (self.move_speed * ursina.held_keys['shift']) - (self.move_speed*.9 * ursina.held_keys['alt'])) * time.dt

        # if ursina.mouse.middle:
        #     if not ursina.camera.orthographic:
        #         zoom_compensation = -self.target_z * .1
        #     else:
        #         zoom_compensation = ursina.camera.orthographic * ursina.camera.fov * .2

        #     self.position -= ursina.camera.right * ursina.mouse.velocity[0] * self.pan_speed[0] * zoom_compensation
        #     self.position -= ursina.camera.up * ursina.mouse.velocity[1] * self.pan_speed[1] * zoom_compensation

        # if not ursina.camera.orthographic:
        #     ursina.camera.z = ursina.lerp(ursina.camera.z, self.target_z, ursina.time.dt*self.zoom_smoothing)
        # else:
        ursina.camera.fov = ursina.lerp(ursina.camera.fov, self.target_fov, ursina.time.dt*self.zoom_smoothing)

        if self.rotation_smoothing == 0:
            self.rotation = self.smoothing_helper.rotation
        else:
            self.quaternion = ursina.slerp(self.quaternion, self.smoothing_helper.quaternion, ursina.time.dt*self.rotation_smoothing)
            ursina.camera.world_rotation_z = 0


    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if hasattr(self, 'smoothing_helper') and name in ('rotation', 'rotation_x', 'rotation_y', 'rotation_z'):
            setattr(self.smoothing_helper, name, value)