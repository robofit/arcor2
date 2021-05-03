from arcor2.exceptions import Arcor2Exception


class LockingException(Arcor2Exception):
    pass


class CannotUnlock(LockingException):
    pass


class CannotLock(LockingException):
    pass
