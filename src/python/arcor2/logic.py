from typing import Optional, Set

from arcor2.cached import CachedProject, CachedProjectException
from arcor2.data.common import Action
from arcor2.exceptions import Arcor2Exception

LogicContainer = CachedProject  # TODO make it Union[CachedProject, CachedProjectFunction]

# TODO def validate_logic() -> to be called before saving project / building the package


def check_for_loops(parent: LogicContainer, first_action_id: Optional[str] = None) -> None:

    visited_actions: Set[str] = set()

    def _check_for_loops(action: Action) -> None:

        if action.id in visited_actions:
            raise Arcor2Exception("Loop detected!")

        visited_actions.add(action.id)

        _, outputs = parent.action_io(action.id)

        for output in outputs:
            if output.end == output.END:
                continue

            _check_for_loops(parent.action(output.end))

    if first_action_id is None:

        try:
            first_action_id = parent.first_action_id()
        except CachedProjectException as e:
            raise Arcor2Exception("Can't check unfinished logic.") from e

    first_action = parent.action(first_action_id)

    _check_for_loops(first_action)
