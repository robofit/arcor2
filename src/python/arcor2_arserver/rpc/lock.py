from websockets.server import WebSocketServerProtocol as WsClient

from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver.lock.exceptions import CannotLock
from arcor2_arserver_data import rpc as srpc


async def write_lock_cb(req: srpc.lock.WriteLock.Request, ui: WsClient) -> None:
    user_name = glob.USERS.user_name(ui)

    if await glob.LOCK.is_write_locked(req.args.object_id, user_name, req.args.lock_tree):
        logger.warn(f"User {user_name} attempted to re-acquire lock for {req.args.object_id}. Pretending it is OK...")
        return

    if not await glob.LOCK.write_lock(req.args.object_id, user_name, req.args.lock_tree, notify=True):
        raise CannotLock(glob.LOCK.ErrMessages.LOCK_FAIL.value)


async def write_unlock_cb(req: srpc.lock.WriteUnlock.Request, ui: WsClient) -> None:
    await glob.LOCK.write_unlock(req.args.object_id, glob.USERS.user_name(ui), notify=True)


async def read_lock_cb(req: srpc.lock.ReadLock.Request, ui: WsClient) -> None:
    # TODO currently unused, maybe delete?
    if not await glob.LOCK.read_lock(req.args.object_id, glob.USERS.user_name(ui)):
        raise CannotLock(glob.LOCK.ErrMessages.LOCK_FAIL.value)


async def read_unlock_cb(req: srpc.lock.ReadUnlock.Request, ui: WsClient) -> None:
    # TODO currently unused, maybe delete?
    await glob.LOCK.read_unlock(req.args.object_id, glob.USERS.user_name(ui))


async def update_lock_cb(req: srpc.lock.UpdateLock.Request, ui: WsClient) -> None:
    await glob.LOCK.update_lock(req.args.object_id, glob.USERS.user_name(ui), req.args.new_type)
