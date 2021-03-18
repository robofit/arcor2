from __future__ import annotations

from typing import Dict, List, Optional, Union

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2_arserver.lock.exceptions import CannotUnlock


class LockEventData:
    __slots__ = "obj_ids", "owner", "lock", "client"

    def __init__(
        self, obj_ids: Union[List[str], str], owner: str, lock: bool = False, client: Optional[WsClient] = None
    ):
        self.obj_ids = obj_ids
        self.owner = owner
        self.lock = lock
        self.client = client


class Data:
    __slots__ = "owners", "count"

    def __init__(self, owner: str) -> None:
        self.owners: List[str] = [owner]
        self.count: int = 1

    def inc_count(self) -> None:
        self.count += 1

    def dec_count(self) -> None:
        self.count -= 1


class LockedObject:
    __slots__ = "read", "write", "tree"

    def __init__(self) -> None:

        # object id: data
        self.read: Dict[str, Data] = {}
        self.write: Dict[str, Data] = {}

        self.tree: bool = False

    def read_lock(self, obj_id: str, owner: str) -> bool:

        if self.tree:
            return False

        if obj_id in self.write:
            return False

        already_locked = obj_id in self.read
        if already_locked:
            self.read[obj_id].owners.append(owner)
            self.read[obj_id].inc_count()
        else:
            self.read[obj_id] = Data(owner)
        return True

    def read_unlock(self, obj_id: str, owner: str) -> None:

        if obj_id not in self.read:
            raise CannotUnlock(f"Object is not read locked by '{owner}'")

        if owner not in self.read[obj_id].owners:
            raise CannotUnlock(f"Object lock is not owned by '{owner}'")

        if self.read[obj_id].count > 1:
            lock_data = self.read[obj_id]
            try:
                lock_data.owners.remove(owner)
            except ValueError:
                raise CannotUnlock(f"'{owner}' does not own read lock for object '{obj_id}'")

            lock_data.dec_count()
        else:
            del self.read[obj_id]

    def write_lock(self, obj_id: str, owner: str, lock_tree: bool) -> bool:

        # TODO maybe exception would be better?
        if self.tree or obj_id in self.write or obj_id in self.read:
            return False

        if lock_tree and (self.read or self.write):
            return False

        self.write[obj_id] = Data(owner)
        self.tree = lock_tree
        return True

    def write_unlock(self, obj_id: str, owner: str) -> None:

        if obj_id not in self.write:
            raise CannotUnlock(f"Object is not write locked by '{owner}'")

        if owner not in self.write[obj_id].owners:
            raise CannotUnlock(f"Object lock is not owned by '{owner}'")

        if self.tree:
            self.tree = False
        del self.write[obj_id]

    def is_empty(self) -> bool:

        return not self.read and not self.write
