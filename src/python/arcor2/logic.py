from arcor2.cached import CachedProject, CachedProjectException
from arcor2.data.common import Action
from arcor2.exceptions import Arcor2Exception

LogicContainer = CachedProject  # TODO make it Union[CachedProject, CachedProjectFunction]

# TODO def validate_logic() -> to be called before saving project / building the package


def check_for_loops(parent: LogicContainer, first_action_id: None | str = None) -> None:
    """Finds loops in logic. Can process even unfinished logic, when first
    action id is provided.

    :param parent:
    :param first_action_id:
    :return:
    """

    def _check_for_loops(action: Action, visited_actions: set[str]) -> None:

        if action.id in visited_actions:
            raise Arcor2Exception("Loop detected!")

        visited_actions.add(action.id)

        _, outputs = parent.action_io(action.id)

        for output in outputs:

            if output.end == output.END:
                continue

            # each possible execution path have its own set of visited actions
            _check_for_loops(parent.action(output.end), visited_actions.copy())

    if first_action_id is None:

        try:
            first_action_id = parent.first_action_id()
        except CachedProjectException as e:
            raise Arcor2Exception("Can't check unfinished logic.") from e

    first_action = parent.action(first_action_id)

    visited_actions: set[str] = set()
    _check_for_loops(first_action, visited_actions)
