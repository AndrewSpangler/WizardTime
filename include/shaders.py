import os
import ursina

class ShaderCollection:
    def __init__(self, target:os.PathLike, config:dict):
        self._shader_files = {}
        self.shaders = {}

        for ent in os.scandir(target):
            if ent.path.endswith(".vert") or ent.path.endswith(".frag"):
                with open(ent.path) as f:
                    self._shader_files[ent.name] = f.read()
            else:
                print(f"Ignoring non-shader file in shader folder {ent.path}")

        print(f"Found {len(self._shader_files)} shader components")

        for k, conf in config.items():
            if conf.get("vertex"):
                conf["vertex"] = self._shader_files[conf.get("vertex")]
            if conf.get("fragment"):
                conf["fragment"] = self._shader_files[conf.get("fragment")]
            
            self.shaders[k] = ursina.Shader(
                language=ursina.Shader.GLSL,
                **conf
            )