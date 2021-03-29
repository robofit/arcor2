from typing import NamedTuple, Optional

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import BareActionPoint, Orientation, Pose, Position
from arcor2.exceptions import Arcor2Exception


def make_pose_rel(parent: Pose, child: Pose) -> Pose:
    """
    :param parent: e.g. scene object
    :param child:  e.g. action point
    :return: relative pose
    """

    return Pose(
        (child.position - parent.position).rotated(parent.orientation, inverse=True),
        Orientation.from_quaternion(parent.orientation.as_quaternion().inverse() * child.orientation.as_quaternion()),
    )


def make_pose_abs(parent: Pose, child: Pose) -> Pose:
    """
    :param parent: e.g. scene object
    :param child:  e.g. action point
    :return: absolute pose
    """

    return Pose(
        (child.position.rotated(parent.orientation) + parent.position),
        Orientation.from_quaternion(parent.orientation.as_quaternion() * child.orientation.as_quaternion()),
    )


class Parent(NamedTuple):

    pose: Pose
    parent_id: Optional[str] = None  # parent of the parent


def get_parent_pose(scene: CScene, project: CProject, parent_id: str) -> Parent:
    """Returns pose of the parent and parent of the parent (if any).

    :param scene:
    :param project:
    :param parent_id:
    :return:
    """

    if parent_id in scene.object_ids:
        parent_obj = scene.object(parent_id)
        if not parent_obj.pose:
            raise Arcor2Exception("Parent object does not have pose!")
        # TODO find parent object in the graph (SceneObject has "children" property)
        return Parent(parent_obj.pose, None)
    elif parent_id in project.action_points_ids:
        ap = project.bare_action_point(parent_id)
        return Parent(Pose(ap.position, Orientation()), ap.parent)
    else:
        raise Arcor2Exception("Unknown parent_id.")


def make_relative_ap_global(scene: CScene, project: CProject, ap: BareActionPoint) -> None:
    """Transforms (in place) relative AP into a global one.

    :param scene:
    :param project:
    :param ap:
    :return:
    """

    if not ap.parent:
        return

    parent = get_parent_pose(scene, project, ap.parent)

    ap.position = make_pose_abs(parent.pose, Pose(ap.position, Orientation())).position
    for ori in project.ap_orientations(ap.id):
        ori.orientation = make_pose_abs(parent.pose, Pose(Position(), ori.orientation)).orientation

    ap.parent = parent.parent_id
    make_relative_ap_global(scene, project, ap)


def make_global_ap_relative(scene: CScene, project: CProject, ap: BareActionPoint, parent_id: str) -> None:
    """Transforms (in place) global AP into a relative one with given parent
    (can be object or another AP).

    :param scene:
    :param project:
    :param ap:
    :param parent_id:
    :return:
    """

    assert project.scene_id == scene.id

    if ap.parent:
        raise Arcor2Exception("Action point already has a parent.")

    def _make_global_ap_relative(parent_id: str) -> None:

        parent = get_parent_pose(scene, project, parent_id)

        if parent.parent_id:
            _make_global_ap_relative(parent.parent_id)

        ap.position = make_pose_rel(parent.pose, Pose(ap.position, Orientation())).position
        for ori in project.ap_orientations(ap.id):
            ori.orientation = make_pose_rel(parent.pose, Pose(Position(), ori.orientation)).orientation

    _make_global_ap_relative(parent_id)
    ap.parent = parent_id


def make_pose_rel_to_parent(scene: CScene, project: CProject, pose: Pose, parent_id: str) -> Pose:
    """Transforms global Pose into Pose that is relative to a given parent (can
    be object or AP).

    :param scene:
    :param project:
    :param pose:
    :param parent_id:
    :return:
    """

    parent = get_parent_pose(scene, project, parent_id)
    if parent.parent_id:
        pose = make_pose_rel_to_parent(scene, project, pose, parent.parent_id)

    return make_pose_rel(parent.pose, pose)


def abs_pose_from_ap_orientation(scene: CScene, project: CProject, orientation_id: str) -> Pose:
    """Returns absolute Pose without modifying anything within the project.

    :param orientation_id:
    :return:
    """

    ap, ori = project.bare_ap_and_orientation(orientation_id)

    pose = Pose(ap.position, ori.orientation)
    parent_id = ap.parent

    while parent_id:
        parent = get_parent_pose(scene, project, parent_id)
        pose = make_pose_abs(parent.pose, pose)
        parent_id = parent.parent_id

    return pose
