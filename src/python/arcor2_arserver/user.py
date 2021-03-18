from typing import Dict, Set

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.exceptions import Arcor2Exception


class Users:
    def __init__(self) -> None:

        self._interfaces: Set[WsClient] = set()
        self._users_ui: Dict[str, int] = {}
        self._ui_users: Dict[int, str] = {}

    @property
    def interfaces(self) -> Set[WsClient]:
        return self._interfaces

    def add_interface(self, ui: WsClient) -> None:
        self._interfaces.add(ui)

    def login(self, user_name: str, ui: WsClient) -> None:

        if user_name in self._users_ui:
            raise Arcor2Exception("Username already exists")

        ui_id = id(ui)
        self._ui_users[ui_id] = user_name
        self._users_ui[user_name] = ui_id

    def logout(self, ui: WsClient) -> None:

        self._interfaces.remove(ui)
        try:
            user_name = self._ui_users[id(ui)]
            del self._users_ui[user_name]
            del self._ui_users[id(ui)]
        except KeyError:  # Login request is after socket registration, UI not registered when login fails
            ...

    def user_name(self, ui: WsClient) -> str:

        return self._ui_users[id(ui)]
