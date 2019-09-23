import select
import sys
from typing import Union, Callable, Any, TYPE_CHECKING
from arcor2.data.events import Event, ProjectStateEvent, ProjectStateEventData, ProjectStateEnum, ActionStateEvent, \
    ActionStateEventData, ActionStateEnum

if TYPE_CHECKING:
    from arcor2.object_types import Generic  # NOQA


def read_stdin(timeout: float = 0.0) -> Union[str, None]:

    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.readline().strip()
    return None


def handle_action(obj_id: str, f: Callable[..., Any], where: ActionStateEnum) -> None:

    print_event(ActionStateEvent(data=ActionStateEventData(obj_id, f.__name__, where)))

    ctrl_cmd = read_stdin()

    if ctrl_cmd == "p":
        print_event(ProjectStateEvent(data=ProjectStateEventData(ProjectStateEnum.PAUSED)))
        while True:
            ctrl_cmd = read_stdin(0.1)
            if ctrl_cmd == "r":
                print_event(ProjectStateEvent(data=ProjectStateEventData(ProjectStateEnum.RESUMED)))
                break


def print_event(event: Event) -> None:
    """
    Used from main script to print event as JSON.
    """

    print(event.to_json())
    sys.stdout.flush()


def action(f: Callable[..., Any]) -> Callable[..., Any]:  # TODO read stdin and pause if requested
    def wrapper(*args: Union["Generic", Any], **kwargs: Any) -> Any:

        # automagical overload for dictionary (allow to get rid of ** in script).
        if len(args) == 2 and isinstance(args[1], dict) and not kwargs:
            kwargs = args[1]
            args = (args[0],)

        handle_action(args[0].name, f, ActionStateEnum.BEFORE)
        res = f(*args, **kwargs)
        handle_action(args[0].name, f, ActionStateEnum.AFTER)
        return res

    return wrapper
