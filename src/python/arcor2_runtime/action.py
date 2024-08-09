import select
import sys
import threading
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Pose, ProjectRobotJoints, StrEnum
from arcor2.data.events import ActionStateAfter, ActionStateBefore, Event, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.object_types.utils import iterate_over_actions
from arcor2.parameter_plugins.utils import plugin_from_instance


class Commands(StrEnum):
    PAUSE: str = "p"
    RESUME: str = "r"
    STEP: str = "s"


ACTION_NAME_ID_MAPPING_ATTR = "_action_name_id_mapping"
AP_ID_ATTR = "_ap_id"


@dataclass
class Globals:
    breakpoints: None | set[str] = None

    pause_on_next_action = threading.Event()  # stepping
    pause = threading.Event()  # regular pausing
    resume = threading.Event()

    # currently executed action(s)
    # thread_id: action_id*, function
    # *might be unknown for projects without logic
    ea: dict[int | None, None | tuple[None | str, Callable]] = field(default_factory=dict)

    depth: dict[int | None, int] = field(default_factory=dict)

    lock: threading.Lock = field(default_factory=threading.Lock)

    disable_action_wrapper: dict[int, bool] = field(default_factory=dict)


g = Globals()


class PackageStateHandler:
    """Singleton class that manages callbacks for PAUSE and RESUME events."""

    _instance = None
    _on_pause_callbacks: list[Callable[..., None]] = []
    _on_resume_callbacks: list[Callable[..., None]] = []
    _instance_lock = threading.Lock()
    _execution_lock = threading.Lock()

    def __init__(self):
        """Forbidden initializer."""
        raise RuntimeError("Call get_instance() instead")

    @classmethod
    def get_instance(cls):
        """Returns the singleton instance of the class."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls.__new__(cls)
        return cls._instance

    def add_on_pause_callback(self, on_pause_callback: Callable[..., None]) -> None:
        """Adds a callback to be executed when the script is paused."""
        self._on_pause_callbacks.append(on_pause_callback)

    def remove_on_pause_callback(self, on_pause_callback: Callable[..., None]) -> None:
        """Removes a callback to be executed when the script is paused."""
        self._on_pause_callbacks.remove(on_pause_callback)

    def add_on_resume_callback(self, on_resume_callback: Callable[..., None]) -> None:
        """Adds a callback to be executed when the script is resumed."""
        self._on_resume_callbacks.append(on_resume_callback)

    def remove_on_resume_callback(self, on_resume_callback: Callable[..., None]) -> None:
        """Removes a callback to be executed when the script is resumed."""
        self._on_resume_callbacks.remove(on_resume_callback)

    def execute_on_pause(self) -> None:
        """Executes all pause callbacks."""
        thread_id = threading.get_ident() if threading.current_thread() is not threading.main_thread() else None

        with self._execution_lock:
            # Disable action wrapper to prevent stack overflow when action is called from PAUSE callback.
            g.disable_action_wrapper[thread_id] = True

            try:
                for callback in self._on_pause_callbacks:
                    callback()
            finally:
                # Enable action wrapper back.
                g.disable_action_wrapper[thread_id] = False

    def execute_on_resume(self) -> None:
        """Executes all resume callbacks."""
        thread_id = threading.get_ident() if threading.current_thread() is not threading.main_thread() else None

        with self._execution_lock:
            # Disable action wrapper to prevent stack overflow when action is called from RESUME callback.
            g.disable_action_wrapper[thread_id] = True

            try:
                for callback in self._on_resume_callbacks:
                    callback()
            finally:
                # Enable action wrapper back.
                g.disable_action_wrapper[thread_id] = False


def patch_aps(project: CachedProject) -> None:
    """orientations / joints have to be monkey-patched with AP's ID in order to
    make breakpoints work in @action."""

    for ap in project.action_points:
        setattr(ap.position, AP_ID_ATTR, ap.id)

        for joints in project.ap_joints(ap.id):
            setattr(joints, AP_ID_ATTR, ap.id)


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


def print_event(event: Event) -> None:
    """Used from main script to print event as JSON."""

    print(event.to_json())
    sys.stdout.flush()


def _get_commands():
    """Reads stdin and checks for commands from parent script (e.g. Execution
    unit). Prints events to stdout. State is signalled using events.

    p == pause script
    r == resume script

    :return:
    """

    while True:
        raw_cmd = read_stdin(0.1)

        if not raw_cmd:
            continue

        cmd = Commands(raw_cmd)

        with g.lock:
            if g.pause.is_set():
                if cmd in (Commands.STEP, Commands.RESUME):
                    g.pause.clear()

                    if cmd == Commands.STEP:
                        g.pause_on_next_action.set()

                    g.resume.set()
            else:
                if cmd == Commands.PAUSE:
                    g.resume.clear()
                    g.pause.set()


_cmd_thread = threading.Thread(target=_get_commands)
_cmd_thread.daemon = True
_cmd_thread.start()


def handle_stdin_commands(*, before: bool, breakpoint: bool = False) -> None:
    """Actual handling of commands in (potentially parallel) actions."""

    with g.lock:
        if (breakpoint or (before and g.pause_on_next_action.is_set())) and not g.pause.is_set():
            g.pause_on_next_action.clear()
            g.resume.clear()
            g.pause.set()

    if g.pause.is_set():
        # Execute on pause callbacks, prevent transfer to PAUSED state if callback causes exception.
        PackageStateHandler.get_instance().execute_on_pause()

        # Signal that thread is paused.
        print_event(PackageState(PackageState.Data(PackageState.Data.StateEnum.PAUSED)))

        # Wait for resume.
        g.resume.wait()

        # Signal that thread is running.
        print_event(PackageState(PackageState.Data(PackageState.Data.StateEnum.RUNNING)))

        # Execute on resume callbacks, if callback causes exception, it is in RUNNING state.
        PackageStateHandler.get_instance().execute_on_resume()


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
        thread_id = threading.get_ident() if threading.current_thread() is not threading.main_thread() else None

        if thread_id not in g.ea:
            g.ea[thread_id] = None

        if thread_id not in g.depth:
            g.depth[thread_id] = 0

        # Execute action without wrapping in case that action wrapper is disabled for this thread.
        if g.disable_action_wrapper.get(thread_id, False):
            g.depth[thread_id] += 1

            try:
                res = f(obj, *action_args, an=an, **kwargs)
            except Arcor2Exception:
                g.depth[thread_id] = 0
                g.ea[thread_id] = None
                raise

            g.depth[thread_id] -= 1
            return res

        try:
            action_id: None | str = None
            action_mapping_provided = hasattr(obj, ACTION_NAME_ID_MAPPING_ATTR)

            inner_action = g.depth[thread_id] > 0

            if not inner_action:  # the following code should be executed only for outermost action
                # do not attempt to get id for inner actions
                try:
                    action_id = getattr(obj, ACTION_NAME_ID_MAPPING_ATTR)[an]
                except AttributeError:
                    # mapping from action name to id not provided, ActionState won't be sent
                    pass
                except KeyError:
                    if an is None:
                        raise Arcor2Exception("Mapping from action name to id provided, but action name not set.")
                    raise Arcor2Exception(f"Mapping from action name to id is missing key {an}.")

                assert g.ea[thread_id] is None

                g.ea[thread_id] = action_id, f

                # collect action point ids, ignore missing
                action_point_ids: set[str] = set()
                for aa in action_args:
                    try:
                        if isinstance(aa, ProjectRobotJoints):
                            action_point_ids.add(getattr(aa, AP_ID_ATTR))
                        elif isinstance(aa, Pose):
                            action_point_ids.add(getattr(aa.position, AP_ID_ATTR))
                    except AttributeError:
                        if g.breakpoints:
                            raise Arcor2Exception("Orientations/Joints not patched. Breakpoints won't work!")

                # validate if break is required
                make_a_break = bool(g.breakpoints and g.breakpoints.intersection(action_point_ids))

                # dispatch ActionStateBefore event for every (outermost) action
                state_before = ActionStateBefore(
                    ActionStateBefore.Data(
                        # TODO deal with kwargs parameters
                        action_id,
                        None,
                        action_point_ids if action_point_ids else None,
                        thread_id,
                    )
                )

                try:
                    state_before.data.parameters = [plugin_from_instance(arg).value_to_json(arg) for arg in action_args]
                except Arcor2Exception:
                    if action_id:
                        # for projects with logic, it should not happen that there is unknown parameter type
                        # for projects without logic (for which we don't know action_id), it is fine...
                        raise

                print_event(state_before)

                handle_stdin_commands(before=True, breakpoint=make_a_break)

            else:  # handle outermost actions
                # if not set (e.g. when writing actions manually), do not attempt to get action IDs from names
                if action_mapping_provided:
                    if an:
                        raise Arcor2Exception("Inner actions should not have name specified.")

                    if not g.ea[thread_id][1].__action__.composite:  # type: ignore
                        # TODO not sure why this was needed, assert was not enough
                        ea_value = cast(tuple[str | None, Callable[..., Any]], g.ea[thread_id])

                        msg = f"Outer action {ea_value[1].__name__}/{ea_value[0]} not flagged as composite."
                        raise Arcor2Exception(msg)

            g.depth[thread_id] += 1

            # the action itself is executed under all circumstances
            try:
                res = f(obj, *action_args, an=an, **kwargs)
            except Arcor2Exception:
                # this is actually not necessary at the moment as when exception is raised, the script ends anyway
                # TODO maybe print ProjectException from here instead of from Resources' context manager?
                # ...could provide action_id from here
                raise

            g.depth[thread_id] -= 1

            # manage situation when we are getting out of (composite) action
            if not inner_action:
                if action_mapping_provided and action_id:  # for projects with logic - check based on action_id
                    # TODO not sure why this was needed, assert was not enough
                    ea_value = cast(tuple[str | None, Callable[..., Any]], g.ea[thread_id])
                    assert ea_value[0] == action_id
                    print_event(ActionStateAfter(ActionStateAfter.Data(action_id, results_to_json(res))))

                g.ea[thread_id] = None

            handle_stdin_commands(before=False)

            return res

        except Arcor2Exception:
            g.depth[thread_id] = 0
            g.ea[thread_id] = None
            raise

    return cast(F, wrapper)
