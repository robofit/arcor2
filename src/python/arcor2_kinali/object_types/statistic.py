from dataclasses import dataclass
from typing import List

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import rest
from arcor2.data.common import ActionMetadata

from .kinali_simple_object import KinaliSimpleObject


@dataclass
class StatisticValue(JsonSchemaMixin):

    value: float
    created: int


class Statistic(KinaliSimpleObject):
    """Statistic Web API Reference (0.3.0)."""

    _ABSTRACT = False

    def get_names(self, group_id: str) -> List[str]:
        """Gets names of all tracked values stored in given group.

        :param group_id:
        :return:
        """
        return rest.get_list_primitive(f"{self.settings.url}/values/{group_id}", str)

    def add_value(self, group_id: str, name: str, value: float) -> None:
        """Logs value with the specified group and name.

        :param group_id:
        :param name:
        :param value:
        :return:
        """

        rest.put(f"{self.settings.url}/values", params={"group_id": group_id, "name": name, "value": value})

    def get_groups(self) -> List[str]:
        """Gets Ids of all stored groups.

        :param name:
        :return:
        """

        return rest.get_list_primitive(f"{self.settings.url}/values", str)

    def get_values(self, group_id: str, name: str, since_timestamp: int = 0) -> List[StatisticValue]:
        """Gets tracked values with the specified name. Values are sorted as
        were added to service.

        :param group_id: Logged value name.
        :param name: Logged value name.
        :param since_timestamp: The date and time, as a UNIX timestamp in nanoseconds, after which created values
                                are returned.
        :return:
        """

        return rest.get_list(
            f"{self.settings.url}/values/{group_id}/{name}", StatisticValue, params={"since_timestamp": since_timestamp}
        )

    def delete_group(self, group_id: str) -> None:
        """Deletes all tracked values stored in given group.

        :param group_id:
        :return:
        """

        rest.delete(f"{self.settings.url}/values/{group_id}")

    get_names.__action__ = ActionMetadata(blocking=True)  # type: ignore
    add_value.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_groups.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_values.__action__ = ActionMetadata(blocking=True)  # type: ignore
    delete_group.__action__ = ActionMetadata(blocking=True)  # type: ignore
