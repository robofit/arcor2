from dataclasses import dataclass
from typing import List

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import rest
from arcor2.data.common import ActionMetadata, StrEnum

from .kinali_simple_object import KinaliSimpleObject


class NotificationLevelEnum(StrEnum):

    INFO: str = "Info"
    WARN: str = "Warn"
    ERROR: str = "Error"


@dataclass
class DialogValue(JsonSchemaMixin):

    title: str
    content: str
    options: List[str]


@dataclass
class NotificationValue(JsonSchemaMixin):

    message: str
    level: NotificationLevelEnum
    created: int


class Interaction(KinaliSimpleObject):
    """REST interface to the Interaction service (0.1.1)."""

    _ABSTRACT = False

    # --- Dialog Controller --------------------------------------------------------------------------------------------

    def add_dialog(self, title: str, content: str, options: List[str]) -> None:
        """Logs value with the specified group and name.

        :param title:
        :param content:
        :param options:
        :return:
        """

        rest.put(f"{self.settings.url}/dialog", params={"title": title, "content": content}, data=options)

    def get_dialog(self) -> DialogValue:
        """Gets names of all tracked values stored in given group.

        :return:
        """

        return rest.get(f"{self.settings.url}/dialog", DialogValue)

    def add_dialog_resolve(self, option: str) -> None:
        """Logs value with the specified group and name.

        :param option:
        :return:
        """

        rest.put(f"{self.settings.url}/dialog/resolve", params={"option": option})

    # --- Notification Controller --------------------------------------------------------------------------------------

    def add_notification(self, message: str, level: NotificationLevelEnum) -> None:
        """Logs value with the specified group and name.

        :param message:
        :param level:
        :return:
        """

        rest.put(f"{self.settings.url}/notification", params={"message": message, "level": level})

    def delete_notifications(self) -> None:
        """Deletes all tracked values stored in given group.

        :return:
        """

        rest.delete(f"{self.settings.url}/notifications")

    def get_notifications(self, since_imestamp: int) -> List[NotificationValue]:
        """Gets names of all tracked values stored in given group.

        :param since_imestamp:
        :return:
        """
        return rest.get_list(
            f"{self.settings.url}/notifications", NotificationValue, params={"since_imestamp": since_imestamp}
        )

    add_dialog.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_dialog.__action__ = ActionMetadata(blocking=True)  # type: ignore
    add_dialog_resolve.__action__ = ActionMetadata(blocking=True)  # type: ignore
    add_notification.__action__ = ActionMetadata(blocking=True)  # type: ignore
    delete_notifications.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_notifications.__action__ = ActionMetadata(blocking=True)  # type: ignore
