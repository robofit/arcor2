from typing import NamedTuple

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedProjectException
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
    parent_id: None | str = None  # parent of the parent


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
        raise Arcor2Exception(f"Unknown parent_id {parent_id}.")


def make_relative_ap_global(scene: CScene, project: CProject, ap: BareActionPoint) -> set[str]:
    """Transforms (in place) relative AP into a global one.

    :param scene:
    :param project:
    :param ap:
    :return:
    """

    if not ap.parent:
        raise Arcor2Exception("Action point does not have a parent.")

    updated_aps: set[str] = set()

    def _update_childs(parent: Parent, ap_id: str) -> None:

        for child_id in project.childs(ap_id):

            try:
                child_ap = project.bare_action_point(child_id)
            except CachedProjectException:
                continue

            child_ap.position = child_ap.position.rotated(parent.pose.orientation)

            for ori in project.ap_orientations(child_ap.id):
                ori.orientation = Orientation.from_quaternion(
                    parent.pose.orientation.as_quaternion() * ori.orientation.as_quaternion()
                )

            updated_aps.add(child_ap.id)
            _update_childs(parent, child_ap.id)

    def _make_relative_ap_global(_ap: BareActionPoint) -> None:

        if not _ap.parent:
            return

        parent = get_parent_pose(scene, project, _ap.parent)

        if parent.pose.orientation != Orientation():
            _update_childs(parent, _ap.id)

        _ap.position = make_pose_abs(parent.pose, Pose(_ap.position, Orientation())).position
        for ori in project.ap_orientations(_ap.id):
            ori.orientation = make_pose_abs(parent.pose, Pose(Position(), ori.orientation)).orientation

        _ap.parent = parent.parent_id
        _make_relative_ap_global(_ap)

    _make_relative_ap_global(ap)
    return updated_aps


def make_global_ap_relative(scene: CScene, project: CProject, ap: BareActionPoint, parent_id: str) -> set[str]:
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

    updated_aps: set[str] = set()
    updated_orientations: set[str] = set()

    def _update_childs(parent: Parent, ap_id: str) -> None:

        for child_id in project.childs(ap_id):

            try:
                child_ap = project.bare_action_point(child_id)
            except CachedProjectException:
                continue

            child_ap.position = child_ap.position.rotated(parent.pose.orientation, inverse=True)

            for ori in project.ap_orientations(child_ap.id):
                ori.orientation = Orientation.from_quaternion(
                    parent.pose.orientation.as_quaternion().inverse() * ori.orientation.as_quaternion()
                )

                updated_orientations.add(ori.id)

            updated_aps.add(child_ap.id)
            _update_childs(parent, child_ap.id)

    def _make_global_ap_relative(parent_id: str) -> None:

        parent = get_parent_pose(scene, project, parent_id)

        if parent.parent_id:
            _make_global_ap_relative(parent.parent_id)

        ap.position = make_pose_rel(parent.pose, Pose(ap.position, Orientation())).position
        for ori in project.ap_orientations(ap.id):
            ori.orientation = make_pose_rel(parent.pose, Pose(Position(), ori.orientation)).orientation

        if parent.pose.orientation != Orientation():
            _update_childs(parent, ap.id)

    _make_global_ap_relative(parent_id)
    ap.parent = parent_id
    return updated_aps


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


def abs_position_from_ap(scene: CScene, project: CProject, ap_id: str) -> Position:
    """Returns absolute Position without modifying anything within the project.

    :param ap_id:
    :return:
    """

    ap = project.bare_action_point(ap_id)
    pose = Pose(ap.position, Orientation())
    parent_id = ap.parent

    while parent_id:
        parent = get_parent_pose(scene, project, parent_id)
        pose = make_pose_abs(parent.pose, pose)
        parent_id = parent.parent_id

    return pose.position
