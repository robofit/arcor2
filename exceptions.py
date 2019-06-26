class Arcor2Exception(Exception):
    """
    All exceptions are derived from this one.
    """
    pass


class WorldObjectException(Arcor2Exception):
    pass


class RobotException(Arcor2Exception):
    pass


class ResourcesException(Exception):
    pass