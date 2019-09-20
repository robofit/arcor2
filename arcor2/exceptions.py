import sys
from arcor2.data.events import ProjectExceptionEvent, ProjectExceptionEventData


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

    pee = ProjectExceptionEvent(data=ProjectExceptionEventData(str(e),
                                                               e.__class__.__name__,
                                                               isinstance(e, Arcor2Exception)))
    print(pee.to_json())
    sys.stdout.flush()
