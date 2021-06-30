from websockets.server import WebSocketServerProtocol as WsClient

from arcor2_arserver import globals as glob
from arcor2_arserver.lock.structures import LockEventData
from arcor2_arserver_data import rpc as srpc


async def register_user_cb(req: srpc.u.RegisterUser.Request, ui: WsClient) -> None:

    await glob.USERS.login(req.args.user_name, ui)
    glob.logger.debug(f"User {req.args.user_name} just logged in. Known user names are: {glob.USERS.user_names}")

    await glob.LOCK.cancel_auto_release(req.args.user_name)

    for user, user_objects in glob.LOCK.all_ui_locks.items():
        if user != req.args.user_name:
            glob.LOCK.notifications_q.put_nowait(LockEventData(user_objects, user, True, ui))

    _, user_write_locks = await glob.LOCK.get_owner_locks(req.args.user_name)
    if user_write_locks:
        glob.LOCK.notifications_q.put_nowait(LockEventData(user_write_locks, req.args.user_name, True, ui))

    return None
