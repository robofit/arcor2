import select
import sys
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Pose, ProjectRobotJoints
from arcor2.data.events import ActionStateAfter, ActionStateBefore, Event, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.object_types.utils import iterate_over_actions
from arcor2.parameter_plugins.utils import plugin_from_instance

ACTION_NAME_ID_MAPPING_ATTR = "_action_name_id_mapping"
AP_ID_ATTR = "_ap_id"

_pause_on_next_action = False
start_paused = False
breakpoints: None | set[str] = None


def patch_object_actions(type_def: type[Generic]) -> None:
    """Dynamically adds @action decorator to the methods with assigned
    ActionMetadata.

    :param type_def: Type to be patched.
    :param action_name_to_id: Mapping from action names (`an` parameter) to action ids.
    :return:
    """

    for method_name, method in iterate_over_actions(type_def):
        # TODO avoid accidental double patching
        setattr(type_def, method_name, action(method))


def patch_with_action_mapping(type_def: type[Generic], scene: CachedScene, project: CachedProject) -> None:

    setattr(
        type_def,
        ACTION_NAME_ID_MAPPING_ATTR,
        {
            act.name: act.id
            for act in project.actions
            if scene.object(act.parse_type().obj_id).type == type_def.__name__
        },
    )


try:
    # Windows solution
    import msvcrt
    import time

    def read_stdin(timeout: float = 0.0) -> str | None:

        time_to_end = time.monotonic() + timeout

        while True:

            if msvcrt.kbhit():  # type: ignore
                return msvcrt.getch().decode()  # type: ignore

            if not timeout or time.monotonic() > time_to_end:
                return None

            time.sleep(timeout / 100.0)

except ImportError:

    # Linux solution
    def read_stdin(timeout: float = 0.0) -> str | None:

        if select.select([sys.stdin], [], [], timeout)[0]:
            return sys.stdin.readline().strip()
        return None


def handle_stdin_commands(*, before: bool, breakpoint: bool = False) -> None:
    """Reads stdin and checks for commands from parent script (e.g. Execution
    unit). Prints events to stdout.

    p == pause script
    r == resume script

    :return:
    """

    global _pause_on_next_action
    global start_paused

    if read_stdin() == "p" or (before and _pause_on_next_action) or start_paused or breakpoint:
        start_paused = False
        print_event(PackageState(PackageState.Data(PackageState.Data.StateEnum.PAUSED)))
        while True:

            cmd = read_stdin(0.1)

            if cmd not in ("s", "r"):
                continue

            _pause_on_next_action = cmd == "s"

            print_event(PackageState(PackageState.Data(PackageState.Data.StateEnum.RUNNING)))
            break


def print_event(event: Event) -> None:
    """Used from main script to print event as JSON."""

    print(event.to_json())
    sys.stdout.flush()


F = TypeVar("F", bound=Callable[..., Any])


def results_to_json(res: Any) -> None | list[str]:
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


# action_id*, function
# *might be unknown for projects without logic
_executed_action: None | tuple[None | str, Callable] = None


def action(f: F) -> F:
    """Action decorator that prints events with action id and parameters or
    results.

    It handles two different situations:
    1) projects with logic, where mapping from 'an' (action name) to action id is provided,
    2) projects without logic, where actions are written manually.

    For 1), it prints out Before (with action_id set) and After events.
    For 2), it prints out only Before event.

    For nested actions, events are printed out only for the outermost one, the inner ones are silenced.

    :param f: action method
    :return:
    """

    @wraps(f)
    def wrapper(obj: Generic, *action_args: Any, an: None | str = None, **kwargs: Any) -> Any:

        # remembers the outermost action
        # when set, serves as a flag, that we are inside an action
        # ...then when another action is executed, we know that it is a nested one (and the outer one is composite)
        global _executed_action

        action_id: None | str = None
        action_mapping_provided = hasattr(obj, ACTION_NAME_ID_MAPPING_ATTR)

        # if not set (e.g. when writing actions manually), do not attempt to get action IDs from names
        if action_mapping_provided:
            if _executed_action and an:
                raise Arcor2Exception("Inner actions should not have name specified.")

            if not _executed_action:  # do not attempt to get id for inner actions
                try:
                    action_id = getattr(obj, ACTION_NAME_ID_MAPPING_ATTR)[an]
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

        if _executed_action is None:  # the following code should be executed only for outermost action
            _executed_action = action_id, f

            # collect action point ids, ignore missing
            action_point_ids: set[str] = set()
            for aa in action_args:
                try:
                    if isinstance(aa, (Pose, ProjectRobotJoints)):
                        action_point_ids.add(getattr(aa, AP_ID_ATTR))
                except AttributeError:
                    if breakpoints:
                        raise Arcor2Exception("Orientations/Joints not patched. Breakpoints won't work!")

            # validate if break is required
            make_a_break = bool(breakpoints and breakpoints.intersection(action_point_ids))

            # dispatch ActionStateBefore event for every (outermost) action
            state_before = ActionStateBefore(
                ActionStateBefore.Data(
                    # TODO deal with kwargs parameters
                    action_id,
                    None,
                    action_point_ids if action_point_ids else None,
                )
            )

            try:
                state_before.data.parameters = [plugin_from_instance(arg).value_to_json(arg) for arg in action_args]
            except Arcor2Exception:
                if action_id:
                    # for projects with logic, it should not happen that there is unknown parameter type
                    # for projects without logic (for which we don't know action_id), it is fine...
                    _executed_action = None
                    raise

            print_event(state_before)

            handle_stdin_commands(before=True, breakpoint=make_a_break)

        # the action itself is executed under all circumstances
        try:
            res = f(obj, *action_args, an=an, **kwargs)
        except Arcor2Exception:
            # this is actually not necessary at the moment as when exception is raised, the script ends anyway
            _executed_action = None
            # TODO maybe print ProjectException from here instead of from Resources' context manager?
            # ...could provide action_id from here
            raise

        # manage situation when we are getting out of (composite) action
        if action_mapping_provided:  # for projects with logic - check based on action_id
            if action_id and _executed_action[0] == action_id:
                _executed_action = None
                print_event(ActionStateAfter(ActionStateAfter.Data(action_id, results_to_json(res))))
        else:  # for projects without logic - can be only based on checking the method
            if _executed_action[1] == f:
                # TODO shouldn't we sent ActionStateAfter even here?
                _executed_action = None

        handle_stdin_commands(before=False)

        return res

    return cast(F, wrapper)
