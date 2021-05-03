from typing import Dict, Set

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.exceptions import Arcor2Exception


class UsersException(Arcor2Exception):
    pass


class Users:
    def __init__(self) -> None:

        self._interfaces: Set[WsClient] = set()
        self._users_ui: Dict[str, int] = {}
        self._ui_users: Dict[int, str] = {}

    def _assert_consistency(self) -> None:

        assert list(self._ui_users.keys()) == list(self._users_ui.values())
        assert list(self._ui_users.values()) == list(self._users_ui.keys())

    @property
    def interfaces(self) -> Set[WsClient]:
        return self._interfaces

    def add_interface(self, ui: WsClient) -> None:
        self._interfaces.add(ui)

    def login(self, user_name: str, ui: WsClient) -> None:

        self._assert_consistency()

        if user_name in self._users_ui:
            raise UsersException("Username already exists")

        ui_id = id(ui)

        self._ui_users[ui_id] = user_name
        self._users_ui[user_name] = ui_id

    def logout(self, ui: WsClient) -> None:
        """Removes ui from known interfaces and logs a user out (if logged in).

        :param ui:
        :return:
        """

        self._assert_consistency()

        try:
            self._interfaces.remove(ui)
        except KeyError:
            raise UsersException("Unknown ui.")

        ui_id = id(ui)

        try:
            user_name = self._ui_users[ui_id]
        except KeyError:
            return

        del self._users_ui[user_name]
        del self._ui_users[ui_id]

    @property
    def user_names(self) -> Set[str]:
        return set(self._users_ui.keys())

    def user_name(self, ui: WsClient) -> str:

        self._assert_consistency()

        try:
            return self._ui_users[id(ui)]
        except KeyError:
            raise UsersException("User not logged in.")
