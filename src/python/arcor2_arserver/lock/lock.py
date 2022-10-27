from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Iterable

from arcor2 import env
from arcor2.cached import CachedProjectException, UpdateableCachedProject, UpdateableCachedScene
from arcor2.data import common as cmn
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver import logger
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.lock.common import ObjIds, obj_ids_to_list
from arcor2_arserver.lock.exceptions import CannotLock, LockingException
from arcor2_arserver.lock.structures import LockedObject, LockEventData
from arcor2_arserver.object_types.data import ObjectTypeDict
from arcor2_arserver_data.rpc.lock import UpdateType


class Lock:
    class Owners(cmn.StrEnum):
        """Values that can be used as lock owner substitution."""

        SERVER: str = "SERVER"

    class SpecialValues(cmn.StrEnum):
        """Values for special locking cases e.g. global variable access."""

        SCENE: str = "SCENE"
        PROJECT: str = "PROJECT"
        RUNNING_ACTION: str = "ACTION"
        ADDING_OBJECT: str = "ADDING_OBJECT"

    class ErrMessages(cmn.StrEnum):
        """Lock general error messages."""

        SOMETHING_LOCKED: str = "There are locked objects"
        SOMETHING_LOCKED_IN_TREE: str = "Part of tree is locked"
        LOCK_FAIL: str = "Locking failed, try again"
        NOT_LOCKED: str = "Object not locked"

    __slots__ = (
        "_scene",
        "_project",
        "_lock",
        "_locked_objects",
        "_release_tasks",
        "notifications_q",
        "_ui_user_locks",
        "_lock_timeout",
        "_lock_retries",
        "_retry_wait",
        "_object_types",
    )

    def __init__(self, obj_types: ObjectTypeDict) -> None:
        self._scene: None | UpdateableCachedScene = None
        self._project: None | UpdateableCachedProject = None
        self._object_types = obj_types

        self._lock: asyncio.Lock = asyncio.Lock()
        self._locked_objects: dict[str, LockedObject] = {}
        self._release_tasks: dict[str, asyncio.Task] = {}

        self.notifications_q: asyncio.Queue[LockEventData] = asyncio.Queue()
        self._ui_user_locks: dict[str, set[str]] = {}

        self._lock_timeout: float = env.get_float("ARCOR2_ARSERVER_LOCK_TIMEOUT", 300)
        self._lock_retries: int = env.get_int("ARCOR2_ARSERVER_LOCK_RETRIES", 13)
        self._retry_wait: float = env.get_float("ARCOR2_ARSERVER_LOCK_RETRY_WAIT", 0.15)

    @property
    def scene(self) -> None | UpdateableCachedScene:
        return self._scene

    @scene.setter
    def scene(self, scene: None | UpdateableCachedScene = None) -> None:
        self._scene = scene

    def scene_or_exception(self, ensure_project_closed: bool = False) -> UpdateableCachedScene:
        if not self._scene:
            raise Arcor2Exception("Scene not opened.")

        if ensure_project_closed and self._project:
            raise Arcor2Exception("Project has to be closed first.")

        return self._scene

    @property
    def project(self) -> None | UpdateableCachedProject:
        return self._project

    @project.setter
    def project(self, project: None | UpdateableCachedProject = None) -> None:
        self._project = project

    def project_or_exception(self, *, must_have_logic: bool = False) -> UpdateableCachedProject:
        if not self._project:
            raise Arcor2Exception("Project not opened.")

        if must_have_logic and not self._project.has_logic:
            raise Arcor2Exception("Project without logic.")

        return self._project

    @property
    def all_ui_locks(self) -> dict[str, set[str]]:
        """All lock grayed-out in editor in format user: {obj_ids}"""

        return self._ui_user_locks

    @asynccontextmanager
    async def get_lock(self, dry_run: bool = False) -> AsyncGenerator[None | asyncio.Lock, None]:
        """Get lock for data structure, method should be used for operation
        with whole scene/project e.g. saving project, where no changes should
        be made during this operation.

        :param dry_run: self._lock is not acquired/blocked when set
        """

        if self._ui_user_locks:
            # TODO turn warn into debug once the issue with "Locking failed" is gone
            if not dry_run:
                logger.warn(f"Locking failed... ui_user_locks: {self._ui_user_locks}")
            raise CannotLock(self.ErrMessages.LOCK_FAIL.value)

        i = 0
        yielded = False
        try:
            for _ in range(self._lock_retries):
                i += 1
                try:
                    async with self._lock:  # TODO maybe use some timeout here?
                        if self._get_write_locks_count():
                            raise CannotLock(self.ErrMessages.LOCK_FAIL.value)

                        if not dry_run:
                            yielded = True
                            yield self._lock
                    if dry_run:
                        yielded = True
                        yield None

                    break
                except CannotLock:
                    await asyncio.sleep(self._retry_wait)
        finally:
            if i > self._lock_retries * 0.25:
                logger.warn(f"Retry took {i * self._lock_timeout}")

            if not yielded:
                # TODO turn warn into debug once the issue with "Locking failed" is gone
                logger.warn(
                    f"Locking failed... locked_objects: {self._locked_objects}, ui_user_locks: {self._ui_user_locks}."
                )
                raise CannotLock(self.ErrMessages.LOCK_FAIL.value)

    async def read_lock(self, obj_ids: ObjIds, owner: str) -> bool:
        """Lock object ids by owner if all checks pass. No object is locked
        otherwise.

        :param obj_ids: object identifiers to be locked
        :param owner: lock owner name
        """

        obj_ids = obj_ids_to_list(obj_ids)
        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            return self._read_lock(roots, obj_ids, owner)

    def _read_lock(self, roots: list[str], obj_ids: Iterable[str], owner: str) -> bool:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        locked: list[str] = []
        for i, obj_id in enumerate(obj_ids):

            if self._get_lock_record(roots[i]).read_lock(obj_id, owner):
                locked.append(obj_id)
            else:
                self._read_unlock(roots, locked, owner)
                return False
        return True

    async def read_unlock(self, obj_ids: ObjIds, owner: str) -> None:
        """Check real lock owner and delete records from lock database.

        :param obj_ids: object identifiers to be unlocked
        :param owner: lock owner name
        """

        obj_ids = obj_ids_to_list(obj_ids)

        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            self._read_unlock(roots, obj_ids, owner)

    def _read_unlock(self, roots: list[str], obj_ids: list[str], owner: str) -> None:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        for i, obj_id in enumerate(obj_ids):
            try:
                self._get_lock_record(roots[i]).read_unlock(obj_id, owner)
            except LockingException:
                self._read_unlock(roots[i + 1 :], obj_ids[i + 1 :], owner)
                raise
            finally:
                self._check_and_clean_root(roots[i])

    async def write_lock(self, obj_ids: ObjIds, owner: str, lock_tree: bool = False, notify: bool = False) -> bool:
        """Lock object or list of objects for writing, possible to lock whole
        tree where object(s) is located.

        :param obj_ids: object or objects to be locked
        :param owner: name of lock owner
        :param lock_tree: boolean whether lock whole tree
        :param notify: if set, broadcast information about locked objects and store those objects in user lock database
        :return: boolean whether lock was successful
        """

        assert isinstance(obj_ids, str) and lock_tree or not lock_tree

        obj_ids = obj_ids_to_list(obj_ids)
        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            ret = self._write_lock(roots, obj_ids, owner, lock_tree)

        if ret and notify:
            ui_locked = set(obj_ids)
            if lock_tree:
                for obj_id in roots:  # TODO lock only tree from affected object
                    ui_locked.update(self.get_all_children(obj_id))
                ui_locked.update(roots)
            self._upsert_user_locked_objects(owner, list(ui_locked))
            self.notifications_q.put_nowait(LockEventData(ui_locked, owner, True))
        return ret

    def _write_lock(self, roots: list[str], obj_ids: Iterable[str], owner: str, lock_tree: bool = False) -> bool:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        locked: list[str] = []
        for i, obj_id in enumerate(obj_ids):

            if self._get_lock_record(roots[i]).write_lock(obj_id, owner, lock_tree):
                locked.append(obj_id)
            else:
                self._write_unlock(roots, locked, owner)
                return False
        return True

    async def write_unlock(self, obj_ids: ObjIds, owner: str, notify: bool = False) -> None:
        """Check object lock real owner and remove it from lock database.

        :param obj_ids: object identifiers to be locked
        :param owner: lock owner name
        :param notify: if set, send-out notification about unlocked objects
        """

        obj_ids = obj_ids_to_list(obj_ids)

        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            locked_trees = self._write_unlock(roots, obj_ids, owner)

        ui_locked = set(obj_ids)
        for obj_id, locked_tree in zip(roots, locked_trees):  # TODO lock only tree from affected object
            if locked_tree:
                ui_locked.update(self.get_all_children(obj_id))
                ui_locked.update(roots)

        # Always try to remove locked objects from database, so it won't get messy when deleting too many objects
        self._remove_user_locked_objects(owner, list(ui_locked))

        if notify:
            self.notifications_q.put_nowait(LockEventData(ui_locked, owner))

    def _write_unlock(self, roots: list[str], obj_ids: list[str], owner: str) -> list[bool]:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        ret: list[bool] = []
        for i, obj_id in enumerate(obj_ids):
            lock_record = self._get_lock_record(roots[i])
            ret.append(lock_record.tree)
            try:
                lock_record.write_unlock(obj_id, owner)

            except LockingException:
                self._write_unlock(roots[i + 1 :], obj_ids[i + 1 :], owner)
                raise
            finally:
                self._check_and_clean_root(roots[i])
        return ret

    async def is_write_locked(self, obj_id: str, owner: str, check_tree_locked: bool = False) -> bool:
        """Checks if object is write locked.

        :param obj_id: object identifiers to be locked
        :param owner: lock owner name
        :param check_tree_locked: if set, checks also if whole tree is locked
        """

        root_id = await self.get_root_id(obj_id)

        async with self._lock:
            return self._is_write_locked(root_id, obj_id, owner, check_tree_locked)

    def _is_write_locked(self, root_id: str, obj_id: str, owner: str, check_tree_locked: bool) -> bool:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        if lock_record := self._locked_objects.get(root_id):

            if obj_id in lock_record.write and owner == lock_record.write[obj_id]:
                if check_tree_locked:
                    return lock_record.tree
                return True

            if lock_record.tree:
                write_locks = lock_record.write.values()

                # When tree is locked, always 1 write lock occurs
                assert len(write_locks) == 1

                return owner == next(iter(write_locks))

        return False

    async def is_read_locked(self, obj_id: str, owner: str) -> bool:
        """Checks if object is locked for read.

        :param obj_id: object identifier to check
        :param owner: user name which must own lock record
        """

        root_id = await self.get_root_id(obj_id)

        async with self._lock:
            return self._is_read_locked(root_id, obj_id, owner)

    def _is_read_locked(self, root_id: str, obj_id: str, owner: str) -> bool:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        if lock_record := self._locked_objects.get(root_id):
            return obj_id in lock_record.read and owner in lock_record.read[obj_id]
        return False

    async def get_locked_roots_count(self) -> int:
        """Count and return number of total locked roots."""

        async with self._lock:
            return len(self._locked_objects)

    async def get_write_locks_count(self) -> int:
        """Count and return total number of write locks."""

        async with self._lock:
            return self._get_write_locks_count()

    def _get_write_locks_count(self) -> int:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        return sum(len(lock.write) for lock in self._locked_objects.values())

    async def get_root_id(self, obj_id: str) -> str:
        """Retrieve root object id for given object. Works also for project and
        scene ID.

        :param obj_id: object to search root for
        """

        if obj_id in self.SpecialValues.set() | self._object_types.keys():
            return obj_id
        elif self.project and self.scene:
            if (
                obj_id
                in {self.scene.id, self.project.id, cmn.LogicItem.START, cmn.LogicItem.END}
                | self.project.parameters_ids
            ):
                return obj_id
            elif obj_id in self.scene.object_ids:
                # TODO implement with scene object hierarchy
                return obj_id
            else:
                parent = self.project.get_parent_id(obj_id)
                ret = parent if parent else obj_id
                try:
                    while parent:
                        parent = self.project.get_parent_id(parent)
                        if parent and parent != ret:
                            ret = parent
                except CachedProjectException:
                    ...
                return ret

        elif self.scene and obj_id in self.scene.object_ids | {self.scene.id}:
            # TODO implement with scene object hierarchy
            return obj_id

        # locking on dashboard, check if scene or project exists
        if obj_id in set.union(*await asyncio.gather(storage.get_scene_ids(), storage.get_project_ids())):
            return obj_id

        raise Arcor2Exception(f"Unknown object '{obj_id}'.")

    def _get_lock_record(self, root_id: str) -> LockedObject:
        """Create and/or retrieve lock record for root_id."""

        assert self._lock.locked()

        if root_id not in self._locked_objects:
            self._locked_objects[root_id] = LockedObject()

        return self._locked_objects[root_id]

    async def update_write_lock(self, locked_obj_id: str, parent_id: str, owner: str):
        """Update lock record of locked object to new root, both objects
        expected to be locked.

        :param locked_obj_id: ID of locked object to be updated
        :param parent_id: ID of previous parent of locked object
        :param owner: name of lock owner
        """

        new_root_id = await self.get_root_id(locked_obj_id)

        async with self._lock:
            self._write_unlock([parent_id], [locked_obj_id], owner)
            self._write_lock([new_root_id], [locked_obj_id], owner)

    def _check_and_clean_root(self, root: str) -> None:
        """Removes top level lock record if read and write attributes are
        empty."""

        assert self._lock.locked()

        if self._locked_objects[root].is_empty():
            del self._locked_objects[root]

    async def schedule_auto_release(self, owner: str) -> None:
        """Creates task for releasing all user locks.

        :param owner: affected user
        """

        self._release_tasks[owner] = asyncio.create_task(self._release_all_owner_locks(owner))

    async def cancel_auto_release(self, owner: str) -> None:
        """Cancel task releasing user locks after timeout. Used after login.

        :param owner: affected user name
        """

        if owner in self._release_tasks:
            self._release_tasks[owner].cancel()
            del self._release_tasks[owner]

    async def _release_all_owner_locks(self, owner: str) -> None:
        """Task planned after user logout. Release all its lock after timeout
        and notify UIs.

        :param owner: unregistered user
        """

        await asyncio.sleep(self._lock_timeout)

        async with self._lock:
            read, write = self._get_owner_locks(owner)

            if read or write:
                logger.warn(f"{len(read)+len(write)} lock(s) of {owner} were just discarded.")

            self._read_unlock(list(read), list(read.values()), owner)
            self._write_unlock(list(write), list(write.values()), owner)

        if to_notify := self._ui_user_locks.pop(owner):
            self.notifications_q.put_nowait(LockEventData(to_notify, owner))

    async def get_owner_locks(self, owner: str) -> tuple[dict[str, str], dict[str, str]]:
        """Finds which locks belongs to owner.

        :param owner: user name
        :return: tuple of read and write locks in format object_id: root id
        """

        async with self._lock:
            return self._get_owner_locks(owner)

    def _get_owner_locks(self, owner: str) -> tuple[dict[str, str], dict[str, str]]:
        """Private method when lock is already acquired."""

        assert self._lock.locked()

        read: dict[str, str] = {}
        write: dict[str, str] = {}

        for root, data in self._locked_objects.items():
            for obj_id, owners in data.read.items():
                if owner in owners:
                    read[obj_id] = root
            for obj_id, w_owner in data.write.items():
                if owner == w_owner:
                    write[obj_id] = root

        return read, write

    def _upsert_user_locked_objects(self, owner: str, obj_ids: Iterable[str]) -> None:
        """Add objects where lock is visible in UI to related database.

        :param owner: user name of locks owner
        :param obj_ids: objects to be added to user lock database
        """

        if owner not in self._ui_user_locks:
            self._ui_user_locks[owner] = set()

        self._ui_user_locks[owner].update(obj_ids)

    def _remove_user_locked_objects(self, owner: str, obj_ids: Iterable[str]) -> None:
        """Remove items where lock is visible in UI from related database.

        :param owner: user name of locks owner
        :param obj_ids: objects to be removed from user lock database
        """

        if owner in self._ui_user_locks:
            self._ui_user_locks[owner].difference_update(obj_ids)

            if not self._ui_user_locks[owner]:
                del self._ui_user_locks[owner]

    def get_all_children(self, obj_id: str) -> set[str]:
        """Recursively find all children of object.

        :param obj_id: parent of all found children
        """

        return self.project.childs(obj_id, recursive=True) if self.project else set()

    def get_all_parents(self, obj_id: str) -> set[str]:
        """Recursively find all parents in tree.

        :param obj_id: object to search parents for
        """

        parents: set[str] = set()
        if self.project:
            parent = self.project.get_parent_id(obj_id)
            while parent:
                parents.add(parent)
                parent = self.project.get_parent_id(parent)
        elif self.scene:
            ...  # TODO implement with scene object hierarchy

        return parents

    async def check_remove(self, obj_id: str, owner: str) -> bool:
        """Check if object can be removed, e.g. no child locked, not in locked
        tree.

        :param obj_id: object id to be checked
        :param owner: user who tries to remove object, returns true if user owns affected lock
        """

        def check_children(_root: str, obj_ids: set[str], read: bool = False) -> bool:
            lock_item = self._locked_objects[_root]
            for _obj_id in obj_ids:
                if read:
                    if owner not in lock_item.read[_obj_id]:
                        return False
                    if lock_item.read[_obj_id].count != 1:
                        return False
                else:
                    if owner != lock_item.write[_obj_id]:
                        return False
            return True

        root_id = await self.get_root_id(obj_id)
        children = self.get_all_children(obj_id)
        children.add(obj_id)

        async with self._lock:
            if lock_record := self._locked_objects.get(root_id):

                if lock_record.tree and owner != next(iter(lock_record.write.values())):
                    return False

                if not check_children(root_id, children.intersection(lock_record.write)):
                    return False
                if not check_children(root_id, children.intersection(lock_record.read), True):
                    return False
                return True

            return False

    TypesWithId = (
        cmn.SceneObject
        | cmn.BareActionPoint
        | cmn.NamedOrientation
        | cmn.ProjectRobotJoints
        | cmn.Action
        | cmn.ProjectParameter
    )

    def get_by_id(self, obj_id: str) -> TypesWithId:
        """Retrive object by it's ID."""

        if self.project:
            try:
                return self.project.get_by_id(obj_id)
            except CachedProjectException:
                ...

        if self.scene:  # TODO update with scene object hierarchy
            if obj_id in self.scene.object_ids:
                return self.scene.object(obj_id)

        raise Arcor2Exception(f"Object ID {obj_id} not found.")

    async def update_lock(self, obj_id: str, owner: str, upgrade_type: UpdateType) -> None:
        """Upgrades lock to locked whole tree or downgrades lock to simple
        object lock.

        :param obj_id: objects which is locked and updated
        :param owner: owner of current lock
        :param upgrade_type: one of available type
        """

        root_id = await self.get_root_id(obj_id)

        async with self._lock:
            if root_id not in self._locked_objects:
                raise LockingException(self.ErrMessages.NOT_LOCKED.value)

            lock_record = self._get_lock_record(root_id)
            if upgrade_type == UpdateType.TREE:
                lock_record.check_upgrade(obj_id, owner)
                lock_record.tree = True

                to_notify = self.get_all_children(root_id)
                to_notify.add(root_id)
                to_notify.remove(obj_id)
                evt = LockEventData(to_notify, owner, True)

                self._upsert_user_locked_objects(owner, to_notify)
            elif upgrade_type == UpdateType.OBJECT:
                lock_record.check_downgrade(obj_id, owner)
                lock_record.tree = False

                to_notify = self.get_all_children(root_id)
                to_notify.add(root_id)
                to_notify -= {obj_id}
                evt = LockEventData(to_notify, owner)

                self._remove_user_locked_objects(owner, to_notify)
            else:
                raise Arcor2Exception("Unknown type of lock upgrade")

            self.notifications_q.put_nowait(evt)

    async def check_lock_tree(self, obj_id: str, owner: str) -> None:
        """Checks if locking whole tree is possible.

        :param obj_id: object id to dry run locking for
        :param owner: owner of dry run lock
        """

        root_id = await self.get_root_id(obj_id)
        children = self.get_all_children(root_id)
        children.add(root_id)

        async with self._lock:
            if lock_record := self._locked_objects.get(root_id):

                for lock in children.intersection(lock_record.write):
                    if owner != lock_record.write[lock]:
                        raise CannotLock(self.ErrMessages.SOMETHING_LOCKED_IN_TREE.value)

                for lock in children.intersection(lock_record.read):
                    if len(lock_record.read[lock]) > 1 or owner not in lock_record.read[lock]:
                        raise CannotLock(self.ErrMessages.SOMETHING_LOCKED_IN_TREE.value)
