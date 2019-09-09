import json
import sys


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


def print_exception(e: Exception) -> None:

    d = {"event": "projectException", "data": {"message": str(e),
                                               "type": e.__class__.__name__,
                                               "handled": isinstance(e, Arcor2Exception)}}
    print(json.dumps(d))
    sys.stdout.flush()
