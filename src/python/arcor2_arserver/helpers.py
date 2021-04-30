from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Set, Union

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.exceptions import Arcor2Exception
from arcor2_arserver import globals as glob
from arcor2_arserver.decorators import retry
from arcor2_arserver.lock.exceptions import CannotLock, LockingException


def unique_name(name: str, existing_names: Set[str]) -> None:

    if not name:
        raise Arcor2Exception("Name has to be set.")

    if name in existing_names:
        raise Arcor2Exception("Name already exists.")


@asynccontextmanager
async def ctx_write_lock(
    obj_ids: Union[str, List[str]], owner: str, auto_unlock: bool = True, dry_run: bool = False
) -> AsyncGenerator[None, None]:
    @retry(exc=CannotLock, tries=glob.LOCK.LOCK_RETRIES, delay=glob.LOCK.RETRY_WAIT)
    async def lock():
        if not await glob.LOCK.write_lock(obj_ids, owner):
            raise CannotLock("Locking failed")

    await lock()
    try:
        yield
    except Arcor2Exception:
        if not dry_run and not auto_unlock:
            await glob.LOCK.write_unlock(obj_ids, owner)
        raise
    finally:
        if dry_run or auto_unlock:
            await glob.LOCK.write_unlock(obj_ids, owner)


@asynccontextmanager
async def ctx_read_lock(
    obj_ids: Union[str, List[str]], owner: str, auto_unlock: bool = True, dry_run: bool = False
) -> AsyncGenerator[None, None]:
    @retry(exc=CannotLock, tries=glob.LOCK.LOCK_RETRIES, delay=glob.LOCK.RETRY_WAIT)
    async def lock():
        if not await glob.LOCK.read_lock(obj_ids, owner):
            raise CannotLock("Locking failed")

    await lock()
    try:
        yield
    except Arcor2Exception:
        if not dry_run and not auto_unlock:
            await glob.LOCK.read_unlock(obj_ids, owner)
        raise
    finally:
        if dry_run or auto_unlock:
            await glob.LOCK.read_unlock(obj_ids, owner)


async def ensure_locked(obj_id: str, ui: WsClient) -> None:
    """Check if object is write locked.

    Read lock check not needed yet.
    """

    if not await glob.LOCK.is_write_locked(obj_id, glob.USERS.user_name(ui)):
        raise LockingException(f"Object is not write locked <{obj_id}>")


async def get_unlocked_objects(obj_ids: Union[str, List[str]], owner: str) -> List[str]:
    """Check if objects are write locked.

    :return: list of objects that are not write locked
    """

    if isinstance(obj_ids, str):
        obj_ids = [obj_ids]

    return [obj_id for obj_id in obj_ids if not await glob.LOCK.is_write_locked(obj_id, owner)]
