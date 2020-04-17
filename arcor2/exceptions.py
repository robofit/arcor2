def _get_message(e: Exception) -> str:

    try:
        arg = e.args[0]
        if isinstance(arg, Exception):
            return _get_message(arg)
        return arg
    except IndexError:
        return "No message available."


class Arcor2Exception(Exception):
    """
    All exceptions are derived from this one.
    """

    @property
    def message(self) -> str:
        """
        Gets the last (most user-oriented) message from the exception.
        :return:
        """

        return _get_message(self)


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
