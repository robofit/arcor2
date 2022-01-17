import asyncio

from websockets.exceptions import WebSocketException
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.exceptions import Arcor2Exception


class UsersException(Arcor2Exception):
    pass


class Users:

    __slots__ = ("_interfaces", "_users_ui", "_ui_users")

    def __init__(self) -> None:

        self._interfaces: set[WsClient] = set()
        self._users_ui: dict[str, WsClient] = {}
        self._ui_users: dict[WsClient, str] = {}

    def _assert_consistency(self) -> None:

        assert list(self._ui_users.keys()) == list(self._users_ui.values())
        assert list(self._ui_users.values()) == list(self._users_ui.keys())
        assert set(self._ui_users).issubset(self._interfaces)

    @property
    def interfaces(self) -> set[WsClient]:
        return self._interfaces

    def add_interface(self, ui: WsClient) -> None:
        self._interfaces.add(ui)

    async def login(self, user_name: str, ui: WsClient) -> None:

        self._assert_consistency()

        if not user_name:
            raise UsersException("Empty user name.")

        if ui not in self._interfaces:
            raise UsersException("Unknown ui.")

        if user_name in self._users_ui:

            old_ui = self._users_ui[user_name]

            try:
                pong_waiter = await old_ui.ping()
                await asyncio.wait_for(pong_waiter, 1.0)
            except (WebSocketException, asyncio.TimeoutError):
                self._users_ui.pop(user_name, None)
                self._ui_users.pop(old_ui, None)
            else:
                raise UsersException("Username already exists")

        self._ui_users[ui] = user_name
        self._users_ui[user_name] = ui

        self._assert_consistency()

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

        if user_name := self._ui_users.pop(ui, None):
            self._users_ui.pop(user_name, None)

        self._assert_consistency()

    @property
    def user_names(self) -> set[str]:
        return set(self._users_ui)

    def user_name(self, ui: WsClient) -> str:

        self._assert_consistency()

        try:
            return self._ui_users[ui]
        except KeyError:
            raise UsersException("User not logged in.")
