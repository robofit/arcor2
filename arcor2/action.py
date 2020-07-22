import select
import sys
from functools import wraps
from typing import Any, Callable, TYPE_CHECKING, TypeVar, Union, cast

from arcor2.data.common import ActionState, ActionStateEnum, PackageState, PackageStateEnum
from arcor2.data.events import ActionStateEvent, Event, PackageStateEvent

HANDLE_ACTIONS = True

if TYPE_CHECKING:
    from arcor2.object_types.abstract import Generic  # NOQA


try:
    # Windows solution
    import msvcrt
    import time

    def read_stdin(timeout: float = 0.0) -> Union[str, None]:

        time_to_end = time.monotonic() + timeout

        while True:

            x = msvcrt.kbhit()  # type: ignore
            if x:
                return msvcrt.getch().decode()  # type: ignore

            if not timeout or time.monotonic() > time_to_end:
                return None

            time.sleep(timeout / 100.0)


except ImportError:

    # Linux solution
    def read_stdin(timeout: float = 0.0) -> Union[str, None]:

        if select.select([sys.stdin], [], [], timeout)[0]:
            return sys.stdin.readline().strip()
        return None


def handle_action(inst: "Generic", f: Callable[..., Any], where: ActionStateEnum) -> None:

    # can't import Service/Generic here (circ. import)
    if hasattr(inst, "id"):
        obj_id = inst.id  # type: ignore
    else:
        obj_id = inst.__class__.__name__

    print_event(ActionStateEvent(data=ActionState(obj_id, f.__name__, where)))

    ctrl_cmd = read_stdin()

    if ctrl_cmd == "p":
        print_event(PackageStateEvent(data=PackageState(PackageStateEnum.PAUSED)))
        while True:
            ctrl_cmd = read_stdin(0.1)
            if ctrl_cmd == "r":
                print_event(PackageStateEvent(data=PackageState(PackageStateEnum.RUNNING)))
                break


def print_event(event: Event) -> None:
    """
    Used from main script to print event as JSON.
    """

    print(event.to_json())
    sys.stdout.flush()


F = TypeVar('F', bound=Callable[..., Any])


def action(f: F) -> F:

    @wraps(f)
    def wrapper(*args: Union["Generic", Any], **kwargs: Any) -> Any:

        # automagical overload for dictionary (allow to get rid of ** in script).
        if len(args) == 2 and isinstance(args[1], dict) and not kwargs:
            kwargs = args[1]
            args = (args[0],)

        if not action.inside_composite and HANDLE_ACTIONS:  # type: ignore
            handle_action(args[0], f, ActionStateEnum.BEFORE)

        if wrapper.__action__.composite:  # type: ignore # TODO and not step_into
            action.inside_composite = f  # type: ignore

        res = f(*args, **kwargs)

        if action.inside_composite == f:  # type: ignore
            action.inside_composite = None  # type: ignore

        if not action.inside_composite and HANDLE_ACTIONS:  # type: ignore
            handle_action(args[0], f, ActionStateEnum.AFTER)

        return res

    return cast(F, wrapper)


action.inside_composite = None  # type: ignore
