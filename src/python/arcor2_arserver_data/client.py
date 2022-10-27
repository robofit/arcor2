import time
from queue import Empty, Queue
from typing import TypeVar

import websocket
from dataclasses_jsonschema import ValidationError

from arcor2 import json
from arcor2.data import events, rpc
from arcor2.data.rpc import get_id
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger
from arcor2_arserver_data import rpc as srpc


class ARServerClientException(Arcor2Exception):
    pass


RR = TypeVar("RR", bound=rpc.common.RPC.Response)


class ARServer:
    """Really simple client for ARServer.

    Instead of having a separate method for each RPC, it has one method
    (call_rpc) which takes instance of Request and returns instance of
    Response.
    """

    def __init__(
        self,
        ws_connection_str: str = "ws://0.0.0.0:6789",
        timeout: float = 3.0,
        event_mapping: None | dict[str, type[events.Event]] = None,
    ):

        self._ws = websocket.WebSocket()
        self._logger = get_logger(__name__)
        self._event_queue: Queue[events.Event] = Queue()
        if event_mapping is None:
            event_mapping = {}

        self.event_mapping = event_mapping

        start_time = time.monotonic()
        while time.monotonic() < start_time + timeout:
            try:
                self._ws.connect(ws_connection_str)
                break
            except ConnectionRefusedError:
                time.sleep(0.25)

        if not self._ws.connected:
            raise ARServerClientException(f"Failed to connect to '{ws_connection_str}'.")

        self._ws.settimeout(timeout)

        system_info = self._call_rpc(srpc.c.SystemInfo.Request(get_id()), srpc.c.SystemInfo.Response).data

        if system_info is None:
            raise ARServerClientException("Failed to get SystemInfo.")

        self._logger.info(f"Connected to server version {system_info.version}.")

        self._supported_rpcs = system_info.supported_rpc_requests

    def call_rpc(self, req: rpc.common.RPC.Request, resp_type: type[RR]) -> RR:

        if req.request not in self._supported_rpcs:
            raise ARServerClientException(f"{req.request} RPC not supported by the server.")

        return self._call_rpc(req, resp_type)

    def _call_rpc(self, req: rpc.common.RPC.Request, resp_type: type[RR]) -> RR:

        self._ws.send(req.to_json())

        # wait for RPC response, put any incoming event into the queue
        while True:
            try:
                recv_dict = json.loads(self._ws.recv())
            except websocket.WebSocketTimeoutException:
                raise ARServerClientException("RPC timeouted.")

            if not isinstance(recv_dict, dict):
                self._logger.debug(f"Invalid data received: {recv_dict}")
                continue

            if "response" in recv_dict:
                break
            elif "event" in recv_dict:
                self._event_queue.put(self.event_mapping[recv_dict["event"]].from_dict(recv_dict))

        try:
            resp = resp_type.from_dict(recv_dict)
        except ValidationError as e:
            self._logger.error(f"Request: {req.to_dict()}, response: {recv_dict}.")
            raise ARServerClientException("RPC response validation failed.") from e

        assert req.id == resp.id
        assert req.request == resp.response
        return resp

    def get_event(self, drop_everything_until: None | type[events.Event] = None) -> events.Event:
        """Returns queued events (if any) or wait until some event arrives.

        :param drop_everything_until: Drop any event until there is one of required type.
        :return:
        """

        while True:

            try:
                evt = self._event_queue.get_nowait()
            except Empty:
                try:
                    recv_dict = json.loads(self._ws.recv())
                except websocket.WebSocketTimeoutException:
                    raise ARServerClientException("Timeouted.")

                if not isinstance(recv_dict, dict):
                    raise ARServerClientException(f"Invalid data received: {recv_dict}")

                if "event" not in recv_dict:
                    raise ARServerClientException(f"Expected event, got: {recv_dict}")
                evt = self.event_mapping[recv_dict["event"]].from_dict(recv_dict)

            if drop_everything_until and not isinstance(evt, drop_everything_until):
                continue

            return evt

    def close(self) -> None:
        self._ws.close()

    def __enter__(self) -> "ARServer":
        return self

    def __exit__(self, *args) -> None:
        self.close()
