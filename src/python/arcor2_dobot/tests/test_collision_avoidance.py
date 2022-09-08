import pytest

from arcor2 import rest
from arcor2.clients import scene_service
from arcor2.data.common import Pose, Position, WebApiError
from arcor2.data.object_type import Box
from arcor2_dobot.dobot import MoveType
from arcor2_dobot.tests.conftest import Urls


def test_collision_avoidance(start_processes: Urls) -> None:

    robot_pose = Pose(Position(10, 10, 10))

    rest.call(
        rest.Method.PUT,
        f"{start_processes.dobot_url}/state/start",
        body=robot_pose,
    )

    assert rest.call(rest.Method.GET, f"{start_processes.dobot_url}/state/started", return_type=bool)

    eef_pose = rest.call(rest.Method.GET, f"{start_processes.dobot_url}/eef/pose", return_type=Pose)

    obj_pose = Pose(eef_pose.position + Position(x=0.05))

    scene_service.upsert_collision(Box("box", 0.01, 0.01, 0.01), obj_pose)
    scene_service.start()

    # moving sideways should be ok
    rest.call(
        rest.Method.PUT,
        f"{start_processes.dobot_url}/eef/pose",
        body=Pose(eef_pose.position + Position(y=0.1), eef_pose.orientation),
        params={"safe": True},
    )
    rest.call(rest.Method.PUT, f"{start_processes.dobot_url}/eef/pose", body=eef_pose, params={"safe": True})

    # with safe+linear -> move through the object should not be ok
    with pytest.raises(WebApiError):
        rest.call(
            rest.Method.PUT,
            f"{start_processes.dobot_url}/eef/pose",
            body=Pose(eef_pose.position + Position(x=0.1), eef_pose.orientation),
            params={"safe": True, "moveType": MoveType.LINEAR},
        )

    # without linear, it should proceed (find a safe path)
    rest.call(
        rest.Method.PUT,
        f"{start_processes.dobot_url}/eef/pose",
        body=Pose(eef_pose.position + Position(x=0.1), eef_pose.orientation),
        params={"safe": True},
    )

    # it should also proceed without safe
    rest.call(
        rest.Method.PUT,
        f"{start_processes.dobot_url}/eef/pose",
        body=eef_pose,
        params={"safe": False, "moveType": MoveType.LINEAR},
    )

    # TODO not sure why this does not raise exception
    # now it should not be able to find safe path
    # scene_service.upsert_collision(Box("box", 1, 1, 1), obj_pose)
    # with pytest.raises(WebApiError):
    #    rest.call(rest.Method.PUT, f"{start_processes.dobot_url}/eef/pose",
    #    body=Pose(eef_pose.position+Position(x=0.1), eef_pose.orientation), params={"safe": True})

    rest.call(
        rest.Method.PUT,
        f"{start_processes.dobot_url}/state/stop",
        body=robot_pose,
    )
    scene_service.stop()
