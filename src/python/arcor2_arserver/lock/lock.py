from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional, Set, Tuple, Union

from arcor2.cached import CachedProjectException, UpdateableCachedProject, UpdateableCachedScene
from arcor2.data import common as cmn
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.lock.exceptions import CannotLock, LockingException
from arcor2_arserver.lock.structures import LockedObject, LockEventData


class Lock:
    class SpecialValues(cmn.StrEnum):
        SERVER_NAME: str = "SERVER"
        SCENE_NAME: str = "SCENE"
        PROJECT_NAME: str = "PROJECT"

        RUNNING_ACTION: str = "ACTION"

    LOCK_TIMEOUT: int = 300  # 5 minutes
    LOCK_RETRIES: int = 10
    RETRY_WAIT: float = 0.2

    def __init__(self) -> None:
        self._scene: Optional[UpdateableCachedScene] = None
        self._project: Optional[UpdateableCachedProject] = None

        self._lock: asyncio.Lock = asyncio.Lock()
        self._locked_objects: Dict[str, LockedObject] = {}
        self._release_tasks: Dict[str, asyncio.Task] = {}

        self.notifications_q: asyncio.Queue[LockEventData] = asyncio.Queue()
        self._ui_user_locks: Dict[str, Set[str]] = {}

    @property
    def scene(self) -> Optional[UpdateableCachedScene]:
        return self._scene

    @scene.setter
    def scene(self, scene: Optional[UpdateableCachedScene] = None) -> None:
        self._scene = scene

    def scene_or_exception(self, ensure_project_closed: bool = False) -> UpdateableCachedScene:
        if not self._scene:
            raise Arcor2Exception("Scene not opened.")

        if ensure_project_closed and self._project:
            raise Arcor2Exception("Project has to be closed first.")

        return self._scene

    @property
    def project(self) -> Optional[UpdateableCachedProject]:
        return self._project

    @project.setter
    def project(self, project: Optional[UpdateableCachedProject] = None) -> None:
        self._project = project

    def project_or_exception(self) -> UpdateableCachedProject:
        if not self._project:
            raise Arcor2Exception("Project not opened.")

        return self._project

    @property
    def all_ui_locks(self) -> Dict[str, Set[str]]:
        return self._ui_user_locks

    @asynccontextmanager
    async def get_lock(self, dry_run: bool = False) -> AsyncGenerator[Optional[asyncio.Lock], None]:
        """Get lock for data structure, method should be used for operation
        with whole scene/project, no others."""

        if dry_run and self._ui_user_locks:
            raise CannotLock("Cannot acquire lock")

        yielded = False
        try:
            for _ in range(self.LOCK_RETRIES):
                try:
                    async with self._lock:
                        if self._get_write_locks_count():
                            raise CannotLock("Cannot acquire lock")

                        if not dry_run:
                            yielded = True
                            yield self._lock
                    if dry_run:
                        yielded = True
                        yield None

                    break
                except CannotLock:
                    await asyncio.sleep(self.RETRY_WAIT)
        finally:
            if not yielded:
                raise CannotLock("Cannot acquire lock")

    async def read_lock(self, obj_ids: Union[List[str], str], owner: str) -> bool:

        if isinstance(obj_ids, str):
            obj_ids = [obj_ids]

        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            return self._read_lock(roots, obj_ids, owner)

    def _read_lock(self, roots: List[str], obj_ids: List[str], owner: str) -> bool:

        assert self._lock.locked()

        locked = []
        for i, obj_id in enumerate(obj_ids):
            lock_record = self._get_lock_record(roots[i])
            acquired = lock_record.read_lock(obj_id, owner)

            if acquired:
                locked.append(obj_id)
            else:
                self._read_unlock(roots, locked, owner)
                return False
        return True

    async def read_unlock(self, obj_ids: Union[List[str], str], owner: str) -> None:

        if isinstance(obj_ids, str):
            obj_ids = [obj_ids]

        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            self._read_unlock(roots, obj_ids, owner)

    def _read_unlock(self, roots: List[str], obj_ids: List[str], owner: str) -> None:
        """Internal function when lock is acquired."""

        assert self._lock.locked()

        for i, obj_id in enumerate(obj_ids):
            lock_record = self._get_lock_record(roots[i])
            try:
                lock_record.read_unlock(obj_id, owner)

            except LockingException:
                self._read_unlock(roots[i + 1 :], obj_ids[i + 1 :], owner)
                raise
            finally:
                self._check_and_clean_root(roots[i])

    async def write_lock(
        self, obj_ids: Union[List[str], str], owner: str, lock_tree: bool = False, notify: bool = False
    ) -> bool:
        """Lock object or list of objects for writing, possible to lock whole
        tree where object(s) is located.

        :param obj_ids: object or objects to be locked
        :param owner: name of lock owner
        :param lock_tree: boolean whether lock whole tree
        :param notify: if set, broadcast information about locked objects and store those objects in user lock database
        :return: boolean whether lock was successful
        """
        # TODO does it make sense to lock list of trees? currently in project only

        if isinstance(obj_ids, str):
            obj_ids = [obj_ids]

        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            ret = self._write_lock(roots, obj_ids, owner, lock_tree)

        if ret and notify:
            ui_locked = obj_ids
            if lock_tree:
                for obj_id in roots:  # TODO lock only tree from affected object
                    ui_locked.extend(self.get_all_children(obj_id))
                ui_locked += roots
            self._upsert_user_locked_objects(owner, ui_locked)
            self.notifications_q.put_nowait(LockEventData(ui_locked, owner, True))
        return ret

    def _write_lock(self, roots: List[str], obj_ids: List[str], owner: str, lock_tree: bool = False) -> bool:

        assert self._lock.locked()

        locked = []
        for i, obj_id in enumerate(obj_ids):
            lock_record = self._get_lock_record(roots[i])
            acquired = lock_record.write_lock(obj_id, owner, lock_tree)

            if acquired:
                locked.append(obj_id)
            else:
                self._write_unlock(roots, locked, owner)
                return False
        return True

    async def write_unlock(self, obj_ids: Union[List[str], str], owner: str, notify: bool = False) -> None:

        if isinstance(obj_ids, str):
            obj_ids = [obj_ids]

        roots = [await self.get_root_id(obj_id) for obj_id in obj_ids]

        async with self._lock:
            locked_trees = self._write_unlock(roots, obj_ids, owner)

        ui_locked = obj_ids
        for obj_id, locked_tree in zip(roots, locked_trees):  # TODO lock only tree from affected object
            if locked_tree:
                ui_locked.extend(self.get_all_children(obj_id))
                ui_locked.extend(roots)

        # Always try to remove locked objects from database, so it won't get messy when deleting too many objects
        self._remove_user_locked_objects(owner, ui_locked)

        if notify:
            self.notifications_q.put_nowait(LockEventData(ui_locked, owner))

    def _write_unlock(self, roots: List[str], obj_ids: List[str], owner: str) -> List[bool]:
        """Internal function when lock is acquired."""

        assert self._lock.locked()

        ret: List[bool] = []
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

    async def is_write_locked(self, obj_id: str, owner: str) -> bool:

        root_id = await self.get_root_id(obj_id)

        async with self._lock:
            lock_record = self._locked_objects.get(root_id)
            if not lock_record:
                return False

            if obj_id in lock_record.write and owner in lock_record.write[obj_id].owners:
                return True

            if lock_record.tree:
                return True
            return False

    async def is_read_locked(self, obj_id: str, owner: str) -> bool:

        root_id = await self.get_root_id(obj_id)

        async with self._lock:
            return self._is_read_locked(root_id, obj_id, owner)

    def _is_read_locked(self, root_id: str, obj_id: str, owner: str) -> bool:

        assert self._lock.locked()

        lock_record = self._locked_objects.get(root_id)
        if not lock_record:
            return False

        return obj_id in lock_record.read and owner in lock_record.read[obj_id].owners

    async def get_locked_roots_count(self) -> int:

        async with self._lock:
            return len(self._locked_objects)

    async def get_write_locks_count(self) -> int:

        async with self._lock:
            return self._get_write_locks_count()

    def _get_write_locks_count(self) -> int:

        assert self._lock.locked()

        return sum(len(lock.write) for lock in self._locked_objects.values())

    async def get_root_id(self, obj_id: str) -> str:
        """Retrieve root object id for given object."""

        if obj_id in (
            self.SpecialValues.SCENE_NAME,
            self.SpecialValues.PROJECT_NAME,
            self.SpecialValues.RUNNING_ACTION,
        ):
            return obj_id

        elif self.project and self.scene:
            if obj_id in (self.scene.id, self.project.id, cmn.LogicItem.START, cmn.LogicItem.END):
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
        if next((True for scene in (await storage.get_scenes()).items if scene.id == obj_id), False):
            return obj_id
        elif next((True for project in (await storage.get_projects()).items if project.id == obj_id), False):
            return obj_id

        raise Arcor2Exception(f"Unknown object '{obj_id}'")

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

        assert self._lock.locked()

        if self._locked_objects[root].is_empty():
            del self._locked_objects[root]

    async def schedule_auto_release(self, owner: str) -> None:

        self._release_tasks[owner] = asyncio.create_task(self._release_all_owner_locks(owner))

    async def cancel_auto_release(self, owner: str) -> None:

        if owner in self._release_tasks:
            self._release_tasks[owner].cancel()
            del self._release_tasks[owner]

    async def _release_all_owner_locks(self, owner: str) -> None:

        await asyncio.sleep(self.LOCK_TIMEOUT)

        unlocked: Set[str] = set()
        async with self._lock:
            read, write = self._get_owner_locks(owner)

            self._read_unlock(list(read), list(read.values()), owner)
            unlocked.update(read.values())
            self._write_unlock(list(write), list(write.values()), owner)
            unlocked.update(write.values())

        if unlocked:
            self.notifications_q.put_nowait(LockEventData(unlocked, owner))

    async def get_owner_locks(self, owner: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Finds which locks belongs to owner
        :return: object_id: root id
        """

        async with self._lock:
            return self._get_owner_locks(owner)

    def _get_owner_locks(self, owner: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Finds which locks belongs to owner
        :return: tuple of dict(object_id: root_id), first one represents read locks, second one write locks
        """

        assert self._lock.locked()

        read: Dict[str, str] = {}
        write: Dict[str, str] = {}

        for root, data in self._locked_objects.items():
            for obj_id, obj_data in data.read.items():
                if owner in obj_data.owners:
                    read[obj_id] = root
            for obj_id, obj_data in data.write.items():
                if owner in obj_data.owners:
                    write[obj_id] = root

        return read, write

    def _upsert_user_locked_objects(self, owner: str, obj_ids: List[str]) -> None:
        """Add objects where lock is visible in UI.

        :param owner: user name of locks owner
        :param obj_ids: objects to be added to user lock database
        """

        if owner not in self._ui_user_locks:
            self._ui_user_locks[owner] = set()

        self._ui_user_locks[owner].update(obj_ids)

    def _remove_user_locked_objects(self, owner: str, obj_ids: List[str]) -> None:
        """Remove items where lock is visible in UI.

        :param owner: user name of locks owner
        :param obj_ids: objects to be removed from user lock database
        """

        if owner in self._ui_user_locks:
            self._ui_user_locks[owner].difference_update(obj_ids)

            if not self._ui_user_locks[owner]:
                del self._ui_user_locks[owner]

    def get_all_children(self, obj_id: str) -> Set[str]:

        ret: List[str] = []
        if self.project:
            childs = self.project.childs(obj_id)
            ret.extend(childs)
            for child in childs:
                ret.extend(self.get_all_children(child))

        return set(ret)

    def get_all_parents(self, obj_id: str) -> Set[str]:

        parents: Set[str] = set()
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
        tree."""

        def check_owner(_root: str, obj_ids: Set[str], read: bool = False) -> bool:
            lock_item = self._locked_objects[_root]
            for _obj_id in obj_ids:
                if read:
                    if owner not in lock_item.read[_obj_id].owners:
                        return False
                    if lock_item.read[_obj_id].count != 1:
                        return False
                else:
                    if owner not in lock_item.write[_obj_id].owners:
                        return False
            return True

        root = await self.get_root_id(obj_id)
        children = self.get_all_children(obj_id)

        async with self._lock:
            if root in self._locked_objects:
                if not check_owner(root, children.intersection(self._locked_objects[root].write)):
                    return False
                if not check_owner(root, children.intersection(self._locked_objects[root].read), True):
                    return False
            return True

    def get_by_id(
        self, obj_id: str
    ) -> Union[cmn.SceneObject, cmn.BareActionPoint, cmn.NamedOrientation, cmn.ProjectRobotJoints, cmn.Action]:

        if self.project:
            try:
                return self.project.get_by_id(obj_id)
            except CachedProjectException:
                ...

        if self.scene:  # TODO update with scene object hierarchy
            if obj_id in self.scene.object_ids:
                return self.scene.object(obj_id)

        raise Arcor2Exception(f"Object ID {obj_id} not found.")
