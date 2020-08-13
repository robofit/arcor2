from __future__ import annotations

import json
import logging
import time
import uuid
from queue import Empty, Queue
from typing import Optional, Type, TypeVar

from dataclasses_jsonschema import ValidationError

import websocket  # type: ignore

from arcor2.data import events, rpc
from arcor2.data.helpers import EVENT_MAPPING
from arcor2.exceptions import Arcor2Exception


class ARServerClientException(Arcor2Exception):
    pass


RR = TypeVar("RR", bound=rpc.common.Response)


def uid() -> int:
    return uuid.uuid4().int


class ARServer:
    """
    Really simple client for ARServer.

    Instead of having a separate method for each RPC, it has one method (call_rpc) which takes instance of Request
    and returns instance of Response.
    """

    def __init__(self, ws_connection_str: str = "ws://0.0.0.0:6789", timeout: float = 3.0):

        self._ws = websocket.WebSocket()
        self._logger = logging.getLogger(__name__)
        self._event_queue: Queue[events.Event] = Queue()

        start_time = time.monotonic()
        while time.monotonic() < start_time + timeout:
            try:
                self._ws.connect(ws_connection_str)
                break
            except ConnectionRefusedError:
                time.sleep(0.25)

        if not self._ws.connected:
            raise ARServerClientException("Failed to connect.")

        self._ws.settimeout(timeout)

        system_info = self._call_rpc(
            rpc.common.SystemInfoRequest(uid()),
            rpc.common.SystemInfoResponse
        ).data

        self._logger.info(f"Connected to server version {system_info.version}.")

        self._supported_rpcs = system_info.supported_rpc_requests

    def call_rpc(self, req: rpc.common.Request, resp_type: Type[RR]) -> RR:

        if req.request not in self._supported_rpcs:
            raise ARServerClientException(f"{req.request} RPC not supported by the server.")

        return self._call_rpc(req, resp_type)

    def _call_rpc(self, req: rpc.common.Request, resp_type: Type[RR]) -> RR:

        self._ws.send(req.to_json())

        # wait for RPC response, put any incoming event into the queue
        while True:
            try:
                recv_dict = json.loads(self._ws.recv())
            except websocket.WebSocketTimeoutException:
                raise ARServerClientException("RPC timeouted.")

            if "response" in recv_dict:
                break
            elif "event" in recv_dict:
                self._event_queue.put(EVENT_MAPPING[recv_dict["event"]].from_dict(recv_dict))

        try:
            resp = resp_type.from_dict(recv_dict)
        except ValidationError as e:
            self._logger.error(f"Request: {req.to_dict()}, response: {recv_dict}.")
            raise ARServerClientException("RPC response validation failed.") from e

        assert req.id == resp.id
        assert req.request == resp.response
        return resp

    def get_event(self, drop_everything_until: Optional[Type[events.Event]] = None) -> events.Event:
        """
        Returns queued events (if any) or wait until some event arrives.
        :param drop_everything_until: Drop any event until there is one of required type.
        :return:
        """

        try:
            evt = self._event_queue.get_nowait()
        except Empty:
            try:
                recv_dict = json.loads(self._ws.recv())
            except websocket.WebSocketTimeoutException:
                raise ARServerClientException("Timeouted.")

            if "event" not in recv_dict:
                raise ARServerClientException(f"Expected event, got: {recv_dict}")
            evt = EVENT_MAPPING[recv_dict["event"]].from_dict(recv_dict)

        if drop_everything_until and not isinstance(evt, drop_everything_until):
            return self.get_event(drop_everything_until)

        return evt

    def close(self) -> None:
        self._ws.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
