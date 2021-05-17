from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Union

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2_arserver.lock.exceptions import CannotUnlock, LockingException


class LockEventData:
    __slots__ = "obj_ids", "owner", "lock", "client"

    def __init__(
        self, obj_ids: Union[Iterable[str], str], owner: str, lock: bool = False, client: Optional[WsClient] = None
    ):
        if isinstance(obj_ids, str):
            self.obj_ids = [obj_ids]
        else:
            self.obj_ids = list(obj_ids)
        self.owner = owner
        self.lock = lock
        self.client = client


class LockedObject:
    __slots__ = "read", "write", "tree"

    def __init__(self) -> None:

        # object id: owners
        self.read: Dict[str, List[str]] = {}
        self.write: Dict[str, str] = {}

        self.tree: bool = False

    def read_lock(self, obj_id: str, owner: str) -> bool:
        """Perform all necessary check if object can be locked and locks it."""

        if self.tree:
            return False

        if obj_id in self.write:
            return False

        already_locked = obj_id in self.read
        if already_locked:
            self.read[obj_id].append(owner)
        else:
            self.read[obj_id] = [owner]
        return True

    def read_unlock(self, obj_id: str, owner: str) -> None:
        """Perform all necessary check if object can be unlocked and unlocks
        it."""

        if obj_id not in self.read:
            raise CannotUnlock(f"Object is not read locked by '{owner}'")

        if owner not in self.read[obj_id]:
            raise CannotUnlock(f"Object lock is not owned by '{owner}'")

        if len(self.read[obj_id]) > 1:
            self.read[obj_id].remove(owner)
        else:
            del self.read[obj_id]

    def write_lock(self, obj_id: str, owner: str, lock_tree: bool) -> bool:
        """Perform all necessary check if object can be locked and locks it."""

        if self.tree or obj_id in self.write or obj_id in self.read:
            return False

        if lock_tree and (self.read or self.write):
            return False

        self.write[obj_id] = owner
        self.tree = lock_tree
        return True

    def write_unlock(self, obj_id: str, owner: str) -> None:
        """Perform all necessary check if object can be unlocked and unlocks
        it."""

        if obj_id not in self.write:
            raise CannotUnlock(f"Object is not write locked by '{owner}'")

        if owner != self.write[obj_id]:
            raise CannotUnlock(f"Object lock is not owned by '{owner}'")

        if self.tree:
            self.tree = False
        del self.write[obj_id]

    def is_empty(self) -> bool:
        """Check if there are any locked objects in current tree."""

        return not self.read and not self.write

    def check_upgrade(self, obj_id: str, owner: str) -> None:
        """Check if lock can be upgraded to whole locked tree."""

        raise_msg = f"Object lock is not owned by '{owner}'"
        if obj_id not in self.write:
            raise LockingException(raise_msg)

        if len(self.write) > 1:
            raise LockingException(raise_msg)

        if owner != self.write[obj_id]:
            raise LockingException(raise_msg)

        if self.tree:
            raise LockingException("Nothing to upgrade")

    def check_downgrade(self, obj_id: str, owner: str) -> None:
        """Check if lock can be downgraded to single object lock."""

        raise_msg = f"Object lock is not owned by '{owner}'"
        if obj_id not in self.write:
            raise LockingException(raise_msg)

        if owner != self.write[obj_id]:
            raise LockingException(raise_msg)

        if not self.tree:
            raise LockingException("Nothing to downgrade")
