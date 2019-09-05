import json
import select
import sys
from typing import Union, Callable, Any, Dict, TYPE_CHECKING

from arcor2.data.common import DataClassEncoder

if TYPE_CHECKING:
    from arcor2.object_types import Generic  # NOQA


def read_stdin(timeout: float = 0.0) -> Union[str, None]:

    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.readline().strip()
    return None


def handle_action(obj_id: str, f: Callable[..., Any], where: str) -> None:

    # TODO turn following into dataclass
    d = {"event": "actionState", "data": {"method": "{}/{}".format(obj_id, f.__name__), "where": where}}
    print_json(d)

    ctrl_cmd = read_stdin()

    if ctrl_cmd == "p":
        print_json({"event": "projectState", "data": {"state": "paused"}})
        while True:
            ctrl_cmd = read_stdin(0.1)
            if ctrl_cmd == "r":
                print_json({"event": "projectState", "data": {"state": "resumed"}})
                break


def print_json(d: Dict[str, Any]) -> None:

    print(json.dumps(d, cls=DataClassEncoder))
    sys.stdout.flush()


def action(f: Callable[..., Any]) -> Callable[..., Any]:  # TODO read stdin and pause if requested
    def wrapper(*args: Union["Generic", Any], **kwargs: Any) -> Any:

        # automagical overload for dictionary (allow to get rid of ** in script).
        if len(args) == 2 and isinstance(args[1], dict) and not kwargs:
            kwargs = args[1]
            args = (args[0],)

        handle_action(args[0].name, f, "before")
        res = f(*args, **kwargs)
        handle_action(args[0].name, f, "after")
        return res

    return wrapper
