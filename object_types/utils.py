import json
import sys
from typing import Union, Dict
import select
from arcor2.data import DataClassEncoder


def read_stdin(timeout=0.0) -> Union[str, None]:

    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.readline().strip()
    return None


def handle_action(obj_id, f, where) -> None:

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


def print_json(d: Dict) -> None:

    print(json.dumps(d, cls=DataClassEncoder))
    sys.stdout.flush()


def action(f):  # TODO read stdin and pause if requested
    def wrapper(*args, **kwargs):

        handle_action(args[0].name, f, "before")
        res = f(*args, **kwargs)
        handle_action(args[0].name, f, "after")
        return res

    return wrapper