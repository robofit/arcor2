import asyncio

from arcor2.clients import scene_service
from arcor2.clients.scene_service import SceneServiceException
from arcor2.data.common import Pose
from arcor2.data.object_type import Models
from arcor2.data.scene import MeshFocusAction
from arcor2.helpers import run_in_executor


async def upsert_collision(model: Models, pose: Pose) -> None:
    await run_in_executor(scene_service.upsert_collision, model, pose)


async def delete_collision_id(collision_id: str) -> None:
    await run_in_executor(scene_service.delete_collision_id, collision_id)


async def collision_ids() -> set[str]:
    return await run_in_executor(scene_service.collision_ids)


async def focus(mfa: MeshFocusAction) -> Pose:
    return await run_in_executor(scene_service.focus, mfa)


async def start() -> None:
    await run_in_executor(scene_service.start)


async def stop() -> None:
    await run_in_executor(scene_service.stop)


async def started() -> bool:
    return await run_in_executor(scene_service.started)


async def delete_all_collisions() -> None:
    await asyncio.gather(*[delete_collision_id(coll_id) for coll_id in await collision_ids()])


__all__ = [
    upsert_collision.__name__,
    delete_collision_id.__name__,
    collision_ids.__name__,
    focus.__name__,
    delete_all_collisions.__name__,
    SceneServiceException.__name__,
    start.__name__,
    stop.__name__,
    started.__name__,
]
