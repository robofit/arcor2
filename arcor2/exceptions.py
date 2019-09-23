class Arcor2Exception(Exception):
    """
    All exceptions are derived from this one.
    """
    pass


class GenericException(Arcor2Exception):
    pass


class RobotException(Arcor2Exception):
    pass


class ResourcesException(Arcor2Exception):
    pass


class ActionPointNotFound(Arcor2Exception):
    pass


class SceneObjectNotFound(Arcor2Exception):
    pass
