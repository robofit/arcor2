import asyncio
from time import sleep

import pytest

from arcor2.cached import UpdateableCachedProject, UpdateableCachedScene
from arcor2.data import common as cmn
from arcor2.data.rpc.common import IdArgs
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver import globals as glob
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.globals import Lock
from arcor2_arserver.helpers import ctx_read_lock
from arcor2_arserver.lock.exceptions import CannotLock, LockingException
from arcor2_arserver.tests.testutils import ars_connection_str, event, event_mapping, lock_object, unlock_object
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id


@pytest.fixture
def lock() -> Lock:
    """Creates lock with initialized scene and project."""
    test = "test"
    lock = Lock({})

    scene = UpdateableCachedScene(cmn.Scene(test, description=test))
    lock.scene = scene
    project = UpdateableCachedProject(cmn.Project(test, lock.scene.id, description=test, has_logic=True))
    lock.project = project

    assert lock.scene == scene
    assert lock.scene_or_exception() == scene

    assert lock.project == project
    assert lock.project_or_exception() == project

    # add some scene and project objects
    test_object = cmn.SceneObject(test, "TestType")
    lock.scene.upsert_object(test_object)
    ap = lock.project.upsert_action_point(cmn.BareActionPoint.uid(), "ap", cmn.Position(0, 0, 0))
    ap_ap = lock.project.upsert_action_point(cmn.BareActionPoint.uid(), "ap_ap", cmn.Position(0, 0, 1), ap.id)
    ap_ap_ap = lock.project.upsert_action_point(cmn.BareActionPoint.uid(), "ap_ap_ap", cmn.Position(0, 0, 2), ap_ap.id)
    lock.project.upsert_action_point(cmn.BareActionPoint.uid(), "ap2", cmn.Position(0, 1, 0))
    ori = cmn.NamedOrientation("ori", cmn.Orientation())
    lock.project.upsert_orientation(ap_ap_ap.id, ori)
    action = cmn.Action("action", "test/type", parameters=[], flows=[])
    lock.project.upsert_action(ap_ap_ap.id, action)
    return lock


@pytest.mark.asyncio
async def test_ctx_read_lock() -> None:
    test = "test"
    user = "user"

    glob.LOCK = Lock({})
    assert await glob.LOCK.get_locked_roots_count() == 0

    glob.LOCK.scene = UpdateableCachedScene(cmn.Scene(test, description=test))
    glob.LOCK.project = UpdateableCachedProject(cmn.Project(test, glob.LOCK.scene.id, description=test, has_logic=True))

    async def patch() -> set[str]:
        return {glob.LOCK.project_or_exception().id, glob.LOCK.scene_or_exception().id}

    storage.get_project_ids = storage.get_scene_ids = patch

    # add some scene and project objects
    test_object = cmn.SceneObject(test, "TestType")
    glob.LOCK.scene.upsert_object(test_object)
    ap = glob.LOCK.project.upsert_action_point(cmn.BareActionPoint.uid(), "ap", cmn.Position(0, 0, 0), test_object.id)
    ap_ap = glob.LOCK.project.upsert_action_point(cmn.BareActionPoint.uid(), "ap_ap", cmn.Position(0, 0, 1), ap.id)

    assert await glob.LOCK.get_locked_roots_count() == 0

    await glob.LOCK.write_lock(ap_ap.id, user, True)

    assert await glob.LOCK.is_write_locked(test_object.id, user)
    assert await glob.LOCK.is_write_locked(ap.id, user)
    assert await glob.LOCK.is_write_locked(ap_ap.id, user)

    async with ctx_read_lock(test_object.id, user):
        pass

    assert await glob.LOCK.is_write_locked(test_object.id, user)
    assert await glob.LOCK.is_write_locked(ap.id, user)
    assert await glob.LOCK.is_write_locked(ap_ap.id, user)


@pytest.mark.asyncio
async def test_base_logic(lock: Lock) -> None:
    assert lock.project

    test = "test"
    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")

    assert not lock._locked_objects
    await lock.write_lock(ap.id, test)
    assert ap.id in lock._locked_objects
    assert not await lock.read_lock(ap.id, "second_user")
    await lock.write_unlock(ap.id, test)

    await lock.write_lock(ap.id, test, True)
    assert not await lock.read_lock(ap.id, test)
    await lock.write_unlock(ap.id, test)
    assert not lock._locked_objects


@pytest.mark.asyncio
async def test_locking_unknown_id(lock: Lock) -> None:
    assert lock.project

    test = "test"

    with pytest.raises(Arcor2Exception):
        await lock.read_lock(test, test)
    assert not lock._locked_objects

    with pytest.raises(Arcor2Exception):
        await lock.write_lock(test, test)
    assert not lock._locked_objects


@pytest.mark.asyncio
async def test_locking_special_names(lock: Lock) -> None:
    assert lock.project

    test = "test"

    with pytest.raises(Arcor2Exception):
        await lock.read_lock(lock.Owners.SERVER, test)
    with pytest.raises(Arcor2Exception):
        await lock.write_lock(lock.Owners.SERVER, test)

    for special_id in lock.SpecialValues:
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


@pytest.mark.asyncio
async def test_unlocking_unknown_or_unlocked(lock: Lock) -> None:
    assert lock.scene
    assert lock.project

    test = "test"

    # exception expected when unlocking unknown object type
    with pytest.raises(Arcor2Exception):
        await lock.read_unlock(test, test)

    with pytest.raises(Arcor2Exception):
        await lock.write_unlock(test, test)

    # exception expected when unlocking not locked object
    with pytest.raises(LockingException):
        await lock.read_unlock(lock.scene.id, test)

    with pytest.raises(LockingException):
        await lock.write_unlock(lock.scene.id, test)

    with pytest.raises(LockingException):
        await lock.read_unlock(lock.scene.id, test)

    with pytest.raises(LockingException):
        await lock.write_unlock(lock.scene.id, test)

    assert not lock._locked_objects


@pytest.mark.asyncio
async def test_whole_lock_yield(lock: Lock) -> None:
    assert lock.scene
    assert lock.project

    test = "test"

    async with lock.get_lock() as val:
        assert isinstance(val, asyncio.Lock)
        assert lock._lock.locked()

    async with lock.get_lock(dry_run=True) as val:
        assert val is None
        assert not lock._lock.locked()

    await lock.write_lock(lock.scene.id, test)
    with pytest.raises(CannotLock):
        async with lock.get_lock():
            pass
    await lock.write_unlock(lock.scene.id, test)


@pytest.mark.asyncio
async def test_recursive_locking(lock: Lock) -> None:
    assert lock.scene
    assert lock.project

    test = "test"

    assert not await lock.is_write_locked(lock.scene.id, test)
    await lock.write_lock(lock.scene.id, test)
    assert await lock.is_write_locked(lock.scene.id, test)
    assert not await lock.is_read_locked(lock.scene.id, test)
    assert not await lock.write_lock(lock.scene.id, test)
    await lock.write_unlock(lock.scene.id, test)

    assert not await lock.is_read_locked(lock.scene.id, test)
    await lock.read_lock(lock.scene.id, test)
    assert await lock.is_read_locked(lock.scene.id, test)
    assert not await lock.is_write_locked(lock.scene.id, test)
    assert await lock.read_lock(lock.scene.id, test)
    await lock.read_unlock(lock.scene.id, test)
    assert not await lock.write_lock(lock.scene.id, test)
    await lock.read_unlock(lock.scene.id, test)

    # Cover negative return when trying to lock tree with something already locked
    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")
    await lock.write_lock(ap_ap.id, test)
    assert not await lock.write_lock(ap.id, test, True)


@pytest.mark.asyncio
async def test_count_methods(lock: Lock) -> None:
    assert lock.scene
    assert lock.project

    test = "test"

    assert await lock.get_locked_roots_count() == 0
    assert await lock.get_write_locks_count() == 0
    await lock.write_lock(lock.scene.id, test)
    assert await lock.get_locked_roots_count() == 1
    assert await lock.get_write_locks_count() == 1
    await lock.write_unlock(lock.scene.id, test)


@pytest.mark.asyncio
async def test_notification_queue(lock: Lock) -> None:
    assert lock.project

    test = "test"

    aps = lock.project.action_points
    tree_ap_ids = [ap.id for ap in aps if ap.name != "ap2"]
    ap_ap_ap = next(ap for ap in aps if ap.name == "ap_ap_ap")
    ori = lock.project.ap_orientations(ap_ap_ap.id)[0]
    action = lock.project.ap_actions(ap_ap_ap.id)[0]

    # test check remove of implicitly locked child
    await lock.write_lock(ap_ap_ap.id, test, True, True)
    assert lock.all_ui_locks
    await check_notification_content(lock, test, tree_ap_ids + [ori.id, action.id])
    await lock.write_unlock(ap_ap_ap.id, test, True)
    await check_notification_content(lock, test, tree_ap_ids + [ori.id, action.id], False)
    assert not lock.all_ui_locks


@pytest.mark.asyncio
async def test_possibility_of_locking_tree(lock: Lock) -> None:
    assert lock.project

    test = "test"
    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")

    await lock.write_lock(ap.id, test)
    with pytest.raises(CannotLock):
        await lock.check_lock_tree(ap_ap.id, "another_user")
    await lock.check_lock_tree(ap_ap.id, test)
    await lock.write_unlock(ap.id, test)
    await lock.check_lock_tree(ap_ap.id, test)

    await lock.read_lock(ap.id, test)
    with pytest.raises(CannotLock):
        await lock.check_lock_tree(ap_ap.id, "another_user")
    await lock.check_lock_tree(ap_ap.id, test)
    await lock.read_unlock(ap.id, test)
    await lock.check_lock_tree(ap_ap.id, test)


@pytest.mark.asyncio
async def test_updating_lock(lock: Lock) -> None:
    assert lock.project

    test = "test"
    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")

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


@pytest.mark.asyncio
async def test_root_getter(lock: Lock) -> None:
    assert lock.scene
    assert lock.project

    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")
    scene_object_id = next(iter(lock.scene.object_ids))

    assert await lock.get_root_id(lock.scene.id) == lock.scene.id
    assert await lock.get_root_id(lock.project.id) == lock.project.id
    assert await lock.get_root_id(scene_object_id) == scene_object_id
    assert await lock.get_root_id(ap_ap.id) == ap.id
    assert await lock.get_root_id(ap.id) == ap.id

    # root getter for scene only
    lock.project = None
    assert await lock.get_root_id(scene_object_id) == scene_object_id


@pytest.mark.asyncio
async def test_auto_release(lock: Lock) -> None:
    assert lock.project

    test = "test"
    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")
    ap_ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap_ap")
    ap2 = next(ap for ap in lock.project.action_points if ap.name == "ap2")
    ori = lock.project.ap_orientations(ap_ap_ap.id)[0]
    action = lock.project.ap_actions(ap_ap_ap.id)[0]

    # Test auto-release of locks and auto locking of child in tree
    lock._lock_timeout = 2
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
    await asyncio.sleep(lock._lock_timeout + 0.5)
    assert await lock.get_write_locks_count() == 0
    assert not await lock.is_read_locked(ap2.id, test)
    await check_notification_content(lock, test, [ap.id, ap_ap.id, ap_ap_ap.id, ori.id, action.id], False)


@pytest.mark.asyncio
async def test_root_getter_without_scene_and_project(lock: Lock) -> None:
    assert lock.scene
    assert lock.project

    scene = lock.scene
    project = lock.project

    lock.project = None
    lock.scene = None

    with pytest.raises(Arcor2Exception):
        lock.scene_or_exception()
    with pytest.raises(Arcor2Exception):
        lock.project_or_exception()

    async def patch() -> set[str]:
        return {project.id, scene.id}

    storage.get_project_ids = storage.get_scene_ids = patch

    assert await lock.get_root_id(project.id) == project.id
    assert await lock.get_root_id(scene.id) == scene.id


@pytest.mark.asyncio
async def test_update_parent(lock: Lock) -> None:
    assert lock.project

    test = "test"
    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")
    ap2 = next(ap for ap in lock.project.action_points if ap.name == "ap2")

    await lock.write_lock([ap_ap.id, ap.id, ap2.id], test)
    ap_ap.parent = ap2.id
    await lock.update_write_lock(ap_ap.id, ap.id, test)
    assert await lock.is_write_locked(ap_ap.id, test)
    assert await lock.is_write_locked(ap2.id, test)
    assert await lock.is_write_locked(ap.id, test)
    await lock.write_unlock([ap2.id, ap_ap.id, ap.id], test)


@pytest.mark.asyncio
async def test_check_remove(lock: Lock) -> None:
    assert lock.project

    test = "test"
    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")
    ap_ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap_ap")
    ori = lock.project.ap_orientations(ap_ap_ap.id)[0]
    action = lock.project.ap_actions(ap_ap_ap.id)[0]

    # test check remove of implicitly locked child
    await lock.write_lock(ap_ap.id, test, True, True)
    assert not await lock.check_remove(ap.id, "second_user")
    assert not await lock.check_remove(ap_ap_ap.id, "second_user")
    assert not await lock.check_remove(ori.id, "second_user")
    assert not await lock.check_remove(action.id, "second_user")

    # check when remove should pass
    for obj_id in (ap_ap.id, ap_ap_ap.id, action.id, ori.id):
        assert await lock.check_remove(obj_id, test)
    await lock.write_unlock(ap_ap.id, test, True)

    # test check remove when some child locked
    for obj_id in (action.id, ori.id):
        await lock.read_lock(obj_id, test)
        assert not await lock.check_remove(ap.id, "second_user")
        await lock.read_unlock(obj_id, test)

        await lock.write_lock(obj_id, test)
        assert not await lock.check_remove(ap.id, "second_user")
        await lock.write_unlock(obj_id, test)
    assert not await lock.check_remove(ap.id, test)

    # when multiple read locks
    await lock.read_lock(ap.id, "second_user")
    await lock.read_lock(ap.id, "third_user")
    assert not await lock.check_remove(ap.id, test)
    await lock.read_lock(ap.id, test)
    assert not await lock.check_remove(ap.id, test)


@pytest.mark.asyncio
async def test_getters(lock: Lock) -> None:
    assert lock.scene
    assert lock.project

    ap = next(ap for ap in lock.project.action_points if ap.name == "ap")
    ap2 = next(ap for ap in lock.project.action_points if ap.name == "ap2")
    ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap")
    ap_ap_ap = next(ap for ap in lock.project.action_points if ap.name == "ap_ap_ap")
    ori = lock.project.ap_orientations(ap_ap_ap.id)[0]
    scene_object = next(iter(lock.scene.objects))

    # test object getter
    for obj in (ori, ap_ap_ap, ap_ap, ap, ap2, scene_object):
        assert lock.get_by_id(obj.id) == obj

    # test parents getter
    parents = lock.get_all_parents(ori.id)
    test_parents = (ap_ap_ap.id, ap_ap.id, ap.id)
    assert len(parents) == len(test_parents)
    for item in test_parents:
        assert item in parents

    # for scene only
    lock.project = None
    assert not lock.get_all_parents(scene_object.id)


async def check_notification_content(
    lock: Lock, owner: str, objects: list[str], lock_notification: bool = True, count: int = 1
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


def test_lock_events(start_processes: None, ars: ARServer, scene: cmn.Scene, project: cmn.Project) -> None:
    assert ars.call_rpc(rpc.p.OpenProject.Request(get_id(), IdArgs(project.id)), rpc.p.OpenProject.Response).result
    prj_evt = event(ars, events.p.OpenProject)

    event(ars, events.s.SceneState)

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
    event(ars2, events.s.SceneState)
    second_ui = "ars2"
    assert ars2.call_rpc(
        rpc.u.RegisterUser.Request(get_id(), rpc.u.RegisterUser.Request.Args(second_ui)),
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
            rpc.lock.WriteLock.Request(get_id(), rpc.lock.WriteLock.Request.Args(obj_id)), rpc.lock.WriteLock.Response
        ).result
        # lock tree
        assert not ars2.call_rpc(
            rpc.lock.WriteLock.Request(get_id(), rpc.lock.WriteLock.Request.Args(obj_id, True)),
            rpc.lock.WriteLock.Response,
        ).result
        # unlock
        assert not ars2.call_rpc(
            rpc.lock.WriteUnlock.Request(get_id(), rpc.lock.WriteUnlock.Request.Args(obj_id)),
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
    event(ars2, events.s.SceneState)
    assert ars2.call_rpc(
        rpc.u.RegisterUser.Request(get_id(), rpc.u.RegisterUser.Request.Args("ars2")),
        rpc.u.RegisterUser.Response,
    ).result
    locked_evt = event(ars2, events.lk.ObjectsLocked)
    assert locked_evt.data.owner == second_ui
    assert len(locked_evt.data.object_ids) == 1
    assert ori.id in locked_evt.data.object_ids
    ars2.close()
