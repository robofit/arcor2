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

    def add_dialog(self, title: str, content: str, options: List[str]) -> str:
        """Creates dialog, block until operator selects one of the options.

        :param title: Dialog title
        :param content: Dialog content
        :param options: Dialog options.
        :return:
        """

        return rest.put_returning_primitive(
            f"{self.settings.url}/dialog", str, params={"title": title, "content": content}, data=options
        )

    def get_dialog(self) -> DialogValue:
        """Returns active dialog (title and options) or error if no dialog is
        active.

        :return:
        """

        return rest.get(f"{self.settings.url}/dialog", DialogValue)

    def resolve_dialog(self, option: str) -> None:
        """Resolves current dialog using one of the options.

        :param option:
        :return:
        """

        rest.put(f"{self.settings.url}/dialog/resolve", params={"option": option})

    # --- Notification Controller --------------------------------------------------------------------------------------

    def add_notification(self, message: str, level: NotificationLevelEnum) -> None:
        """Creates notification.

        :param message:
        :param level:
        :return:
        """

        rest.put(f"{self.settings.url}/notification", params={"message": message, "level": level})

    def delete_notifications(self) -> None:
        """Clears all notifications.

        :return:
        """

        rest.delete(f"{self.settings.url}/notifications")

    def get_notifications(self, since_timestamp: int) -> List[NotificationValue]:
        """Gets all notifications stored after given timestamp.

        :param since_timestamp: UNIX timestamp in nanoseconds, after which created notifications are returned.
        :return:
        """
        return rest.get_list(
            f"{self.settings.url}/notifications", NotificationValue, params={"sinceTimestamp": since_timestamp}
        )

    add_dialog.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_dialog.__action__ = ActionMetadata(blocking=True)  # type: ignore
    resolve_dialog.__action__ = ActionMetadata(blocking=True)  # type: ignore
    add_notification.__action__ = ActionMetadata(blocking=True)  # type: ignore
    delete_notifications.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_notifications.__action__ = ActionMetadata(blocking=True)  # type: ignore
