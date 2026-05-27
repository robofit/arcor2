import time
from pathlib import Path

from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Mesh
from arcor2_scene_data import scene_service
from arcor2_storage import client as storage_client
from arcor2_ur.common import EffectorType, GraspableState, GraspPosition
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls

MESH_PATH = Path(__file__).parents[1] / "test_mesh_object" / "triangle_block.stl"
MESH_ASSET_ID = "triangle_block.stl"


def test_pick_and_place_mesh_by_position(start_processes: Urls) -> None:
    assert MESH_PATH.is_file(), f"Test mesh file does not exist: {MESH_PATH}"

    storage_client.URL = start_processes.storage_url

    storage_client.create_asset(
        MESH_ASSET_ID,
        MESH_PATH.read_bytes(),
        description="Test mesh for UR5e collision avoidance.",
    )

    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    X = 0.0
    Y = 0.5
    Z = 0.1

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))
    assert len(ot.robot_joints()) == 6

    object = Mesh("Mesh1", MESH_ASSET_ID)
    scene_service.upsert_graspable(object, Pose(Position(X, Y, Z), Orientation(0, 0, 0, 1)), GraspableState.WORLD)
    time.sleep(1)

    ot.pick_up_object_by_position(Position(X, Y, Z), 0.5, EffectorType.SUCK, GraspPosition.TOP)

    assert ot.graspable_state(object.id) == GraspableState.ATTACHED

    ot.place_object(Pose(Position(Y, X, Z), Orientation(0, 0, 0, 1)))

    assert Position(Y, X, Z).distance(ot.graspable_position(object.id)) < 0.03
    assert ot.graspable_state(object.id) == GraspableState.WORLD
    scene_service.delete_all_collisions()
    ot.cleanup()
