import asyncio

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver.lock.structures import LockEventData
from arcor2_arserver.rpc.objects import object_aiming_prune
from arcor2_arserver_data import rpc as srpc


async def register_user_cb(req: srpc.u.RegisterUser.Request, ui: WsClient) -> None:

    await glob.USERS.login(req.args.user_name, ui)
    logger.debug(f"User {req.args.user_name} just logged in. Known user names are: {glob.USERS.user_names}")

    await glob.LOCK.cancel_auto_release(req.args.user_name)

    # those are locks that are known for all users
    for user, user_objects in glob.LOCK.all_ui_locks.items():
        if user != req.args.user_name:
            glob.LOCK.notifications_q.put_nowait(LockEventData(user_objects, user, True, ui))

    # these locks are known only to the current user
    if user_write_locks := (await glob.LOCK.get_owner_locks(req.args.user_name))[1]:
        glob.LOCK.notifications_q.put_nowait(LockEventData(user_write_locks, req.args.user_name, True, ui))

    asyncio.create_task(object_aiming_prune())

    return None
