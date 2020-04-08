import socket
import asyncio
from typing import Union, Text, Tuple

from arcor2.server.globals import PORT
from arcor2.data.common import BroadcastInfo

BROADCAST_PORT: int = 6006


def get_ip() -> str:

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except socket.error:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def get_broadcast() -> str:

    ip = get_ip()
    ip_arr = ip.split(".")
    ip_arr[-1] = "255"
    return ".".join(ip_arr)


Address = Tuple[str, int]


class BroadcastProtocol(asyncio.DatagramProtocol):

    def __init__(self, target: Address, *, loop: asyncio.AbstractEventLoop = None):
        self.target = target
        self.loop = asyncio.get_event_loop() if loop is None else loop

    def connection_made(self, transport):
        self.transport = transport
        sock: socket.socket = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast()

    def datagram_received(self, data: Union[bytes, Text], addr: Address):
        pass

    def broadcast(self):
        self.transport.sendto(BroadcastInfo(socket.gethostname(), PORT).to_json().encode(), self.target)
        self.loop.call_later(1, self.broadcast)


def main():

    loop = asyncio.get_event_loop()

    broadcast_coro = loop.create_datagram_endpoint(lambda: BroadcastProtocol((get_broadcast(), BROADCAST_PORT),
                                                                             loop=loop),
                                                   local_addr=('0.0.0.0', BROADCAST_PORT))

    loop.run_until_complete(broadcast_coro)
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    main()
