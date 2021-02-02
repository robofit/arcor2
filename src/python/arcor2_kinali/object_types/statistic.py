from dataclasses import dataclass
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import rest
from arcor2.data.common import ActionMetadata

from .abstract_simple import AbstractSimple


@dataclass
class StatisticValue(JsonSchemaMixin):

    value: float
    created: int


class Statistic(AbstractSimple):
    """Statistic Web API Reference (0.3.0)."""

    _ABSTRACT = False

    def get_names(self, group_id: str, *, an: Optional[str] = None) -> List[str]:
        """Gets names of all tracked values stored in given group.

        :param group_id:
        :return:
        """
        return rest.call(rest.Method.GET, f"{self.settings.url}/values/{group_id}", list_return_type=str)

    def add_value(self, group_id: str, name: str, value: float, *, an: Optional[str] = None) -> None:
        """Logs value with the specified group and name.

        :param group_id:
        :param name:
        :param value:
        :return:
        """

        rest.call(
            rest.Method.PUT, f"{self.settings.url}/values", params={"group_id": group_id, "name": name, "value": value}
        )

    def get_groups(self, *, an: Optional[str] = None) -> List[str]:
        """Gets Ids of all stored groups.

        :param name:
        :return:
        """

        return rest.call(rest.Method.GET, f"{self.settings.url}/values", list_return_type=str)

    def get_values(
        self, group_id: str, name: str, since_timestamp: int = 0, *, an: Optional[str] = None
    ) -> List[StatisticValue]:
        """Gets tracked values with the specified name. Values are sorted as
        were added to service.

        :param group_id: Logged value name.
        :param name: Logged value name.
        :param since_timestamp: The date and time, as a UNIX timestamp in nanoseconds, after which created values
                                are returned.
        :return:
        """

        return rest.call(
            rest.Method.GET,
            f"{self.settings.url}/values/{group_id}/{name}",
            list_return_type=StatisticValue,
            params={"since_timestamp": since_timestamp},
        )

    def delete_group(self, group_id: str, *, an: Optional[str] = None) -> None:
        """Deletes all tracked values stored in given group.

        :param group_id:
        :return:
        """

        rest.call(rest.Method.DELETE, f"{self.settings.url}/values/{group_id}")

    get_names.__action__ = ActionMetadata(blocking=True)  # type: ignore
    add_value.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_groups.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_values.__action__ = ActionMetadata(blocking=True)  # type: ignore
    delete_group.__action__ = ActionMetadata(blocking=True)  # type: ignore
