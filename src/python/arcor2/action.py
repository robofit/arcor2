import select
import sys
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union, cast

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.events import ActionStateAfter, ActionStateBefore, Event, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.object_types.utils import iterate_over_actions
from arcor2.parameter_plugins.utils import plugin_from_instance

HANDLE_ACTIONS = True  # setting this to False disables checking for commands and printing out events


def get_action_name_to_id(scene: CachedScene, project: CachedProject, object_type: str) -> Dict[str, str]:
    return {act.name: act.id for act in project.actions if scene.object(act.parse_type().obj_id).type == object_type}


def patch_object_actions(type_def: Type[Generic], action_name_to_id: Optional[Dict[str, str]] = None) -> None:
    """Dynamically adds @action decorator to the methods with assigned
    ActionMetadata.

    :param type_def: Type to be patched.
    :param action_name_to_id: Mapping from action names (`an` parameter) to action ids.
    :return:
    """

    # we somehow need to make action name->id accessible within the @action decorator
    if action_name_to_id is not None:
        type_def.action_name_to_id = action_name_to_id  # type: ignore

    for method_name, method in iterate_over_actions(type_def):
        # TODO avoid accidental double patching
        setattr(type_def, method_name, action(method))


try:
    # Windows solution
    import msvcrt
    import time

    def read_stdin(timeout: float = 0.0) -> Union[str, None]:

        time_to_end = time.monotonic() + timeout

        while True:

            if msvcrt.kbhit():  # type: ignore
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


def handle_stdin_commands() -> None:
    """Reads stdin and checks for commands from parent script (e.g. Execution
    unit). Prints events to stdout.

    p == pause script
    r == resume script

    :return:
    """

    if read_stdin() != "p":
        return

    print_event(PackageState(PackageState.Data(PackageState.Data.StateEnum.PAUSED)))
    while True:
        if read_stdin(0.1) == "r":
            print_event(PackageState(PackageState.Data(PackageState.Data.StateEnum.RUNNING)))
            break


def print_event(event: Event) -> None:
    """Used from main script to print event as JSON."""

    print(event.to_json())
    sys.stdout.flush()


F = TypeVar("F", bound=Callable[..., Any])


def results_to_json(res: Any) -> Optional[List[str]]:
    """Prepares action results into list of JSONs. Return value could be tuple
    or single value.

    :param res:
    :return:
    """

    if res is None:
        return None

    if isinstance(res, tuple):
        return [plugin_from_instance(r).value_to_json(r) for r in res]
    else:
        return [plugin_from_instance(res).value_to_json(res)]


_executed_action: Optional[Tuple[str, Callable]] = None


def action(f: F) -> F:
    """Action decorator that prints events with action id and parameters or
    results.

    :param f: action method
    :return:
    """

    @wraps(f)
    def wrapper(*args: Union[Generic, Any], an: Optional[str] = None, **kwargs: Any) -> Any:

        global _executed_action

        action_args = args[1:]
        action_id: Optional[str] = None

        if HANDLE_ACTIONS:  # if not set, ignore everything

            if _executed_action and an:
                raise Arcor2Exception("Inner actions should not have name specified.")

            if not _executed_action:  # do not attempt to get id for inner actions
                try:
                    action_id = args[0].action_name_to_id[an]  # type: ignore
                except AttributeError:
                    # mapping from action name to id not provided, ActionState won't be sent
                    pass
                except KeyError:
                    if an is None:
                        raise Arcor2Exception("Mapping from action name to id provided, but action name not set.")
                    raise Arcor2Exception(f"Mapping from action name to id is missing key {an}.")

            if _executed_action and not _executed_action[1].__action__.composite:  # type: ignore
                msg = f"Outer action {_executed_action[1].__name__}/{_executed_action[0]} not flagged as composite."
                _executed_action = None
                raise Arcor2Exception(msg)

            if action_id:  # can't do much without action_id
                print_event(
                    ActionStateBefore(
                        ActionStateBefore.Data(
                            # TODO deal with kwargs parameters
                            action_id,
                            [plugin_from_instance(arg).value_to_json(arg) for arg in action_args],
                        )
                    )
                )

                if _executed_action is None:
                    _executed_action = action_id, f

        handle_stdin_commands()

        try:
            res = f(*args, an=an, **kwargs)
        except Arcor2Exception:
            # this is actually not necessary at the moment as when exception is raised, the script ends anyway
            _executed_action = None
            # TODO maybe print ProjectException from here instead of from Resources' context manager?
            # ...could provide action_id from here
            raise

        if HANDLE_ACTIONS:
            if action_id:
                # we are getting out of (composite) action
                if _executed_action and _executed_action[0] == action_id:
                    _executed_action = None
                    print_event(ActionStateAfter(ActionStateAfter.Data(action_id, results_to_json(res))))

        handle_stdin_commands()

        return res

    return cast(F, wrapper)
