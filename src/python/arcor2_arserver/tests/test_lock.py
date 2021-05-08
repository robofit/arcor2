import asyncio
import datetime
from time import sleep
from typing import List

import pytest

from arcor2.cached import UpdateableCachedProject, UpdateableCachedScene
from arcor2.clients import persistent_storage as storage
from arcor2.data import common as cmn
from arcor2.data.rpc.common import IdArgs
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver.globals import Lock
from arcor2_arserver.lock.exceptions import CannotLock, CannotUnlock, LockingException
from arcor2_arserver.tests.conftest import ars_connection_str, event, event_mapping, lock_object, unlock_object
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, uid


def test_lock_events(start_processes: None, ars: ARServer, scene: cmn.Scene, project: cmn.Project) -> None:

    assert ars.call_rpc(rpc.p.OpenProject.Request(uid(), IdArgs(project.id)), rpc.p.OpenProject.Response).result
    prj_evt = event(ars, events.p.OpenProject)
    prj = prj_evt.data.project

    # get default project objects
    ap = next(ap for ap in prj.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in prj.action_points if ap.name == "ap_ap")
    ap_ap_ap = next(ap for ap in prj.action_points if ap.name == "ap_ap_ap")
    ori = ap_ap_ap.orientations[0]

    lock_object(ars, ap.id, True)

    # lock object and expect event about it on newly logged UI
    ars2 = ARServer(ars_connection_str(), timeout=30, event_mapping=event_mapping)
    event(ars2, events.p.OpenProject)
    second_ui = "ars2"
    assert ars2.call_rpc(
        rpc.u.RegisterUser.Request(uid(), rpc.u.RegisterUser.Request.Args(second_ui)),
        rpc.u.RegisterUser.Response,
    ).result
    locked_evt = event(ars2, events.lk.ObjectsLocked)
    assert locked_evt.data.owner == "testUser"
    for obj_id in (ap.id, ap_ap.id, ap_ap_ap.id, ori.id):
        assert obj_id in locked_evt.data.object_ids

    # attempt to lock/unlock objects locked by someone else
    for obj_id in (ap.id, ap_ap.id, ap_ap_ap.id, ori.id):
        # lock
        assert not ars2.call_rpc(
            rpc.lock.WriteLock.Request(uid(), rpc.lock.WriteLock.Request.Args(obj_id)), rpc.lock.WriteLock.Response
        ).result
        # lock tree
        assert not ars2.call_rpc(
            rpc.lock.WriteLock.Request(uid(), rpc.lock.WriteLock.Request.Args(obj_id, True)),
            rpc.lock.WriteLock.Response,
        ).result
        # unlock
        assert not ars2.call_rpc(
            rpc.lock.WriteUnlock.Request(uid(), rpc.lock.WriteUnlock.Request.Args(obj_id)),
            rpc.lock.WriteUnlock.Response,
        ).result

    unlock_object(ars, ap.id)
    event(ars2, events.lk.ObjectsUnlocked)

    # test lock will stay locked after logout for a while
    lock_object(ars2, ori.id)
    event(ars, events.lk.ObjectsLocked)

    ars2.close()

    # wait for some time
    sleep(2)  # TODO fill this sleep with another actions

    # register again and check if objects still locked
    ars2 = ARServer(ars_connection_str(), timeout=30, event_mapping=event_mapping)
    event(ars2, events.p.OpenProject)
    assert ars2.call_rpc(
        rpc.u.RegisterUser.Request(uid(), rpc.u.RegisterUser.Request.Args("ars2")),
        rpc.u.RegisterUser.Response,
    ).result
    locked_evt = event(ars2, events.lk.ObjectsLocked)
    assert locked_evt.data.owner == second_ui
    assert len(locked_evt.data.object_ids) == 1
    assert ori.id in locked_evt.data.object_ids
    ars2.close()


async def check_notification_content(
    lock: Lock, owner: str, objects: List[str], lock_notification: bool = True, count: int = 1
) -> None:
    for _ in range(count):
        assert not lock.notifications_q.empty()
        item = await lock.notifications_q.get()
        assert len(item.obj_ids) == len(objects)
        for obj_id in objects:
            assert obj_id in item.obj_ids
        assert item.owner == owner
        assert lock_notification == item.lock
    assert lock.notifications_q.empty()


@pytest.mark.asyncio()
async def test_lock_coverage_and_regression() -> None:
    """This is simple pytest, which can be run without pants.

    Test purpose is to check all real usage of lock class.
    """
    test = "test"
    lock = Lock()

    # patch lock storage functions to pass test
    test_scene = UpdateableCachedScene(cmn.Scene(test, desc=test))
    test_project = UpdateableCachedProject(cmn.Project(test, test_scene.id, desc=test, has_logic=True))

    storage.get_projects = lambda: cmn.IdDescList(
        items=[cmn.IdDesc(test_project.id, test_project.name, datetime.datetime.now(), test_project.desc)]
    )
    storage.get_scenes = lambda: cmn.IdDescList(
        items=[cmn.IdDesc(test_scene.id, test_scene.name, datetime.datetime.now(), test_scene.desc)]
    )

    # Test rest of lock with some scene and project objects
    test_object = cmn.SceneObject(test, "TestType")
    test_scene.upsert_object(test_object)
    ap = test_project.upsert_action_point(cmn.BareActionPoint.uid(), "ap", cmn.Position(0, 0, 0))
    ap_ap = test_project.upsert_action_point(cmn.BareActionPoint.uid(), "ap_ap", cmn.Position(0, 0, 1), ap.id)
    ap_ap_ap = test_project.upsert_action_point(cmn.BareActionPoint.uid(), "ap_ap_ap", cmn.Position(0, 0, 2), ap_ap.id)
    ap2 = test_project.upsert_action_point(cmn.BareActionPoint.uid(), "ap2", cmn.Position(0, 1, 0))
    ori = cmn.NamedOrientation("ori", cmn.Orientation())
    test_project.upsert_orientation(ap_ap_ap.id, ori)
    action = cmn.Action("action", "test/type", parameters=[], flows=[])
    test_project.upsert_action(ap_ap_ap.id, action)

    # test root getters for storage projects and scenes
    assert await lock.get_root_id(test_scene.id) == test_scene.id
    assert await lock.get_root_id(test_project.id) == test_project.id

    # locking special names
    for special_id in lock.SpecialValues:
        # server is used only as lock owner
        if special_id == lock.SpecialValues.SERVER_NAME:
            with pytest.raises(Arcor2Exception):
                await lock.read_lock(special_id, test)
            with pytest.raises(Arcor2Exception):
                await lock.write_lock(special_id, test)
        else:
            await lock.read_lock(special_id, test)
            assert special_id in lock._locked_objects
            assert special_id in lock._locked_objects[special_id].read
            await lock.read_unlock(special_id, test)
            assert not lock._locked_objects

            await lock.write_lock(special_id, test)
            assert special_id in lock._locked_objects
            assert special_id in lock._locked_objects[special_id].write
            await lock.write_unlock(special_id, test)
            assert not lock._locked_objects

    # exception expected when locking unknown object type
    with pytest.raises(Arcor2Exception):
        await lock.read_lock(test, test)
    assert not lock._locked_objects

    with pytest.raises(Arcor2Exception):
        await lock.write_lock(test, test)
    assert not lock._locked_objects

    # exception expected when unlocking unknown object type
    with pytest.raises(Arcor2Exception):
        await lock.read_unlock(test, test)

    with pytest.raises(Arcor2Exception):
        await lock.write_unlock(test, test)

    # exception expected when unlocking not locked object
    with pytest.raises(LockingException):
        await lock.read_unlock(test_scene.id, test)

    with pytest.raises(LockingException):
        await lock.write_unlock(test_scene.id, test)

    with pytest.raises(LockingException):
        await lock.read_unlock(test_scene.id, test)

    with pytest.raises(LockingException):
        await lock.write_unlock(test_scene.id, test)

    assert not lock._locked_objects

    # test whole lock yield
    async with lock.get_lock() as val:
        assert isinstance(val, asyncio.Lock)
        assert lock._lock.locked()

    async with lock.get_lock(dry_run=True) as val:
        assert val is None
        assert not lock._lock.locked()

    await lock.write_lock(test_scene.id, test)
    with pytest.raises(CannotLock):
        async with lock.get_lock():
            pass
    await lock.write_unlock(test_scene.id, test)

    # locking already locked object
    assert not await lock.is_write_locked(test_scene.id, test)
    await lock.write_lock(test_scene.id, test)
    assert await lock.is_write_locked(test_scene.id, test)
    assert not await lock.is_read_locked(test_scene.id, test)
    assert not await lock.write_lock(test_scene.id, test)
    await lock.write_unlock(test_scene.id, test)

    assert not await lock.is_read_locked(test_scene.id, test)
    await lock.read_lock(test_scene.id, test)
    assert await lock.is_read_locked(test_scene.id, test)
    assert not await lock.is_write_locked(test_scene.id, test)
    assert await lock.read_lock(test_scene.id, test)
    await lock.read_unlock(test_scene.id, test)
    assert not await lock.write_lock(test_scene.id, test)
    await lock.read_unlock(test_scene.id, test)

    # testing count returning methods
    assert await lock.get_locked_roots_count() == 0
    assert await lock.get_write_locks_count() == 0
    await lock.write_lock(test_scene.id, test)
    assert await lock.get_locked_roots_count() == 1
    assert await lock.get_write_locks_count() == 1
    await lock.write_unlock(test_scene.id, test)

    # test lock properties
    with pytest.raises(Arcor2Exception):
        lock.scene_or_exception()
    lock.scene = test_scene
    assert lock.scene == test_scene
    assert lock.scene_or_exception() == test_scene

    with pytest.raises(Arcor2Exception):
        lock.project_or_exception()
    lock.project = test_project
    assert lock.project == test_project
    assert lock.project_or_exception() == test_project

    # test rest of lock structures lines with real scene and project ids for change
    await lock.write_lock(test_scene.id, test)
    assert not await lock.read_lock(test_scene.id, "second_user")
    with pytest.raises(CannotUnlock):
        await lock.read_unlock(test_scene.id, "second_user")
    await lock.write_unlock(test_scene.id, test)
    await lock.write_lock(test_scene.id, test, True)
    assert not await lock.read_lock(test_scene.id, test)
    await lock.write_unlock(test_scene.id, test)
    await lock.read_lock(test_scene.id, test)
    with pytest.raises(CannotUnlock):
        await lock.read_unlock(test_scene.id, "second_user")
    await lock.read_unlock(test_scene.id, test)

    await lock.write_lock(test_scene.id, test)
    with pytest.raises(CannotUnlock):
        await lock.write_unlock(test_scene.id, "second_user")
    await lock.write_unlock(test_scene.id, test)

    # Test root getter for different object types
    assert await lock.get_root_id(test_object.id) == test_object.id
    assert await lock.get_root_id(ap_ap.id) == ap.id
    assert await lock.get_root_id(ap.id) == ap.id

    # Cover negative return when trying to lock tree with something already locked
    await lock.write_lock(ap_ap.id, test)
    assert not await lock.write_lock(ap.id, test, True)
    await lock.write_unlock(ap_ap.id, test)

    # Test update of lock
    await lock.write_lock([ap_ap.id, ap.id, ap2.id], test)
    ap_ap.parent = ap2.id
    await lock.update_write_lock(ap_ap.id, ap.id, test)
    assert await lock.is_write_locked(ap_ap.id, test)
    assert await lock.is_write_locked(ap2.id, test)
    assert await lock.is_write_locked(ap.id, test)
    await lock.write_unlock([ap2.id, ap_ap.id, ap.id], test)
    ap_ap.parent = ap.id  # revert

    # Test auto-release of locks and auto locking of child in tree
    lock.LOCK_TIMEOUT = 2
    await lock.write_lock(ap.id, test, True, True)
    assert await lock.is_write_locked(ap_ap_ap.id, test)
    assert await lock.is_write_locked(ap_ap.id, test)
    await check_notification_content(lock, test, [ap.id, ap_ap.id, ap_ap_ap.id, ori.id, action.id])

    await lock.read_lock(ap2.id, test)
    await lock.schedule_auto_release(test)
    await lock.cancel_auto_release(test)
    assert await lock.is_write_locked(ap.id, test)
    assert await lock.is_read_locked(ap2.id, test)

    read, write = await lock.get_owner_locks(test)
    assert len(read) == 1
    assert ap2.id in read
    assert len(write) == 1
    assert ap.id in write

    await lock.schedule_auto_release(test)
    await asyncio.sleep(lock.LOCK_TIMEOUT + 0.5)
    assert await lock.get_write_locks_count() == 0
    assert not await lock.is_read_locked(ap2.id, test)
    await check_notification_content(lock, test, [ap.id, ap_ap.id, ap_ap_ap.id, ori.id, action.id], False)

    # test check remove of implicitly locked child
    await lock.write_lock(ap_ap.id, test, True, True)
    assert not await lock.check_remove(ap.id, "second_user")
    assert not await lock.check_remove(ap_ap_ap.id, "second_user")
    assert not await lock.check_remove(ori.id, "second_user")
    assert not await lock.check_remove(action.id, "second_user")

    # test if ui events are queued
    assert lock.all_ui_locks
    await check_notification_content(lock, test, [ap.id, ap_ap.id, ap_ap_ap.id, ori.id, action.id])
    await lock.write_unlock(ap_ap.id, test, True)
    await check_notification_content(lock, test, [ap.id, ap_ap.id, ap_ap_ap.id, ori.id, action.id], False)
    assert not lock.all_ui_locks

    # test check remove when some child locked
    for obj_id in (action.id, ori.id):
        await lock.read_lock(obj_id, test)
        assert not await lock.check_remove(ap.id, "second_user")
        await lock.read_unlock(obj_id, test)

        await lock.write_lock(obj_id, test)
        assert not await lock.check_remove(ap.id, "second_user")
        await lock.write_unlock(obj_id, test)
    assert not await lock.check_remove(ap.id, test)

    # check when remove should pass
    await lock.write_lock(ap_ap.id, test, True)
    for obj_id in (ap_ap.id, ap_ap_ap.id, action.id, ori.id):
        assert await lock.check_remove(obj_id, test)
    await lock.write_unlock(ap_ap.id, test, True)

    # test object getter
    for obj in (ori, ap_ap_ap, ap_ap, ap, ap2):
        assert lock.get_by_id(obj.id) == obj

    # test parents getter
    parents = lock.get_all_parents(ori.id)
    test_parents = (ap_ap_ap.id, ap_ap.id, ap.id)
    assert len(parents) == len(test_parents)
    for item in test_parents:
        assert item in parents

    # test scene property exception
    with pytest.raises(Arcor2Exception):
        lock.scene_or_exception(True)

    # test lock upgrade and downgrade
    with pytest.raises(LockingException):
        await lock.update_lock(ap.id, test, rpc.lock.UpdateType.TREE)

    await lock.write_lock([ap.id, ap_ap.id], test)
    with pytest.raises(LockingException):
        await lock.update_lock(ap.id, test, rpc.lock.UpdateType.TREE)
    await lock.write_unlock(ap_ap.id, test)
    with pytest.raises(LockingException):
        await lock.update_lock(ap_ap.id, test, rpc.lock.UpdateType.TREE)
    await lock.update_lock(ap.id, test, rpc.lock.UpdateType.TREE)
    with pytest.raises(LockingException):
        await lock.update_lock(ap.id, test, rpc.lock.UpdateType.TREE)
    with pytest.raises(LockingException):
        await lock.update_lock(ap.id, "other_user", rpc.lock.UpdateType.TREE)

    with pytest.raises(LockingException):
        await lock.update_lock(ap_ap.id, test, rpc.lock.UpdateType.OBJECT)
    with pytest.raises(LockingException):
        await lock.update_lock(ap.id, "other_user", rpc.lock.UpdateType.OBJECT)
    await lock.update_lock(ap.id, test, rpc.lock.UpdateType.OBJECT)
    with pytest.raises(LockingException):
        await lock.update_lock(ap.id, test, rpc.lock.UpdateType.OBJECT)
    await lock.write_unlock(ap.id, test)

    # test function checking whether locking tree is possible
    await lock.write_lock(ap.id, test)
    with pytest.raises(CannotLock):
        await lock.check_lock_tree(ap_ap.id)
    await lock.write_unlock(ap.id, test)
    assert await lock.check_lock_tree(ap_ap.id) is None

    # test some other calls for scene only
    lock.project = None
    assert lock.get_by_id(test_object.id) == test_object
    assert not lock.get_all_parents(test_object.id)
    assert await lock.get_root_id(test_object.id) == test_object.id
