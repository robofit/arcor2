import asyncio
from typing import List

import pytest

from arcor2.cached import UpdateableCachedProject, UpdateableCachedScene
from arcor2.data import common as cmn
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver.globals import Lock
from arcor2_arserver.lock.exceptions import CannotLock, CannotUnlock, LockingException


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
    """this is simple pytest, which can be run without pants."""
    test = "test"
    lock = Lock(True)

    # locking scene name
    scene_id = lock.SpecialValues.SCENE_NAME
    await lock.read_lock(scene_id, test)
    assert scene_id in lock._locked_objects
    assert scene_id in lock._locked_objects[scene_id].read
    await lock.read_unlock(scene_id, test)
    assert not lock._locked_objects

    # locking project name
    project_id = lock.SpecialValues.PROJECT_NAME
    await lock.write_lock(project_id, test)
    assert project_id in lock._locked_objects
    assert project_id in lock._locked_objects[project_id].write
    await lock.write_unlock(project_id, test)
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
        await lock.read_unlock(scene_id, test)

    with pytest.raises(LockingException):
        await lock.write_unlock(scene_id, test)

    with pytest.raises(LockingException):
        await lock.read_unlock(project_id, test)

    with pytest.raises(LockingException):
        await lock.write_unlock(project_id, test)

    assert not lock._locked_objects

    # test whole lock yield
    async with lock.get_lock() as val:
        assert isinstance(val, asyncio.Lock)
        assert lock._lock.locked()

    async with lock.get_lock(dry_run=True) as val:
        assert val is None
        assert not lock._lock.locked()

    await lock.write_lock(scene_id, test)
    with pytest.raises(CannotLock):
        async with lock.get_lock():
            pass
    await lock.write_unlock(scene_id, test)

    # locking already locked object
    assert not await lock.is_write_locked(scene_id, test)
    await lock.write_lock(scene_id, test)
    assert await lock.is_write_locked(scene_id, test)
    assert not await lock.is_read_locked(scene_id, test)
    assert not await lock.write_lock(scene_id, test)
    await lock.write_unlock(scene_id, test)

    assert not await lock.is_read_locked(scene_id, test)
    await lock.read_lock(scene_id, test)
    assert await lock.is_read_locked(scene_id, test)
    assert not await lock.is_write_locked(scene_id, test)
    assert await lock.read_lock(scene_id, test)
    await lock.read_unlock(scene_id, test)
    assert not await lock.write_lock(scene_id, test)
    await lock.read_unlock(scene_id, test)

    # testing count returning methods
    assert await lock.get_locked_roots_count() == 0
    assert await lock.get_write_locks_count() == 0
    await lock.write_lock(scene_id, test)
    assert await lock.get_locked_roots_count() == 1
    assert await lock.get_write_locks_count() == 1
    await lock.write_unlock(scene_id, test)

    # test lock properties
    with pytest.raises(Arcor2Exception):
        lock.scene_or_exception()
    test_scene = UpdateableCachedScene(cmn.Scene(test, desc=test))
    lock.scene = test_scene
    assert lock.scene == test_scene
    assert lock.scene_or_exception() == test_scene

    with pytest.raises(Arcor2Exception):
        lock.project_or_exception()
    test_project = UpdateableCachedProject(cmn.Project(test, test_scene.id, desc=test, has_logic=True))
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

    # Test rest of lock with some scene and project objects
    test_object = cmn.SceneObject(test, "TestType")
    test_scene.upsert_object(test_object)
    ap = test_project.upsert_action_point(cmn.BareActionPoint.uid(), "ap", cmn.Position(0, 0, 0))
    ap_ap = test_project.upsert_action_point(cmn.BareActionPoint.uid(), "ap_ap", cmn.Position(0, 0, 1), ap.id)
    ap2 = test_project.upsert_action_point(cmn.BareActionPoint.uid(), "ap2", cmn.Position(0, 1, 0))
    # TODO add and test action, orientation

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

    # Test auto-release of locks
    lock.LOCK_TIMEOUT = 2
    await lock.write_lock(ap.id, test, True, True)
    await check_notification_content(lock, test, [ap.id, ap_ap.id])

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
    await check_notification_content(lock, test, [ap.id, ap_ap.id], False)

    # test check remove
    # await lock.write_lock(ap2.id, test, True)
    # assert not await lock.check_remove(ap_ap.id, test)  # TODO find out why this fails

    # TODO need scene/project with objects
    # test database of ui locked objects
    assert not lock.all_ui_locks


# TODO test na eventy uzivatelum
# TODO test na auto_unlock=False pripady
