import asyncio

import pytest

from arcor2.exceptions import Arcor2Exception
from arcor2_arserver.globals import LOCK as lock
from arcor2_arserver.lock.exceptions import CannotLock, LockingException


@pytest.mark.asyncio()
async def test_lock_basic() -> None:
    test = "test"

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
        with pytest.raises(CannotLock):
            async with lock.get_lock():
                pass
        assert lock._lock.locked()

    async with lock.get_lock(dry_run=True) as val:
        assert val is None

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


# @pytest.mark.asyncio()
# def test_lock_with_scene(scene: common.Scene) -> None:
#     # test locking with active scene
#     ...
#
#
# @pytest.mark.asyncio()
# def test_lock_with_project(project: common.Project) -> None:
#     # test locking with prefilled all project objects
#     ...
