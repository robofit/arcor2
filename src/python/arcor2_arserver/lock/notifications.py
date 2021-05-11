from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver_data import events as sevts


async def run_lock_notification_worker() -> None:
    while True:
        notif_data = await glob.LOCK.notifications_q.get()
        obj_ids = notif_data.obj_ids
        data = sevts.lk.LockData(obj_ids, notif_data.owner)

        evt = sevts.lk.ObjectsLocked(data) if notif_data.lock else sevts.lk.ObjectsUnlocked(data)

        if notif_data.client:
            await notif.event(notif_data.client, evt)
        else:
            await notif.broadcast_event(evt)
