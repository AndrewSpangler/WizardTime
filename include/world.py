# Classes to hold and handle world data and state

# NYI

class World:
    def __init__(self, name:str, config:dict):
        self.name = name
        self.config = config
        self.load_first_level()

    def load_first_level(self) -> None:
        pass


class Level:
    def __init__(self, name:str, world:World, config:dict):
        self.name = name
        self.world = world
        self.config = config
        self.load_first_room()

    def load_first_room(self) -> None:
        pass


class Room:
    def __init__(self, name:str, level:Level, config:dict):
        self.name = name
        self.level = level
        self.config = config
        self.load()

    def load(self) -> None:
        pass