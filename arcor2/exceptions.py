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


class ApNotFound(Arcor2Exception):
    pass
