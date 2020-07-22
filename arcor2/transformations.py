from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Orientation, Pose, Position, ProjectActionPoint
from arcor2.exceptions import Arcor2Exception


def make_position_rel(parent: Position, child: Position) -> Position:

    p = Position()

    p.x = child.x - parent.x
    p.y = child.y - parent.y
    p.z = child.z - parent.z
    return p


def make_orientation_rel(parent: Orientation, child: Orientation) -> Orientation:

    p = Orientation()
    p.set_from_quaternion(child.as_quaternion() / parent.as_quaternion())
    return p


def make_pose_rel(parent: Pose, child: Pose) -> Pose:
    """
    :param parent: e.g. scene object
    :param child:  e.g. action point
    :return: relative pose
    """

    p = Pose()
    p.position = make_position_rel(parent.position, child.position).rotated(parent.orientation, True)
    p.orientation = make_orientation_rel(parent.orientation, child.orientation)
    return p


def make_position_abs(parent: Position, child: Position) -> Position:

    p = Position()
    p.x = child.x + parent.x
    p.y = child.y + parent.y
    p.z = child.z + parent.z
    return p


def make_orientation_abs(parent: Orientation, child: Orientation) -> Orientation:

    p = Orientation()
    p.set_from_quaternion(child.as_quaternion() * parent.as_quaternion().conjugate().inverse())
    return p


def make_pose_abs(parent: Pose, child: Pose) -> Pose:
    """
    :param parent: e.g. scene object
    :param child:  e.g. action point
    :return: absolute pose
    """

    p = Pose()
    p.position = child.position.rotated(parent.orientation)
    p.position = make_position_abs(parent.position, p.position)
    p.orientation = make_orientation_abs(parent.orientation, child.orientation)
    return p


def make_relative_ap_global(scene: CachedScene, project: CachedProject, ap: ProjectActionPoint) -> None:
    """
    Transforms (in place) relative AP into a global one.
    :param scene:
    :param project:
    :param ap:
    :return:
    """

    if not ap.parent:
        return

    if ap.parent in scene.object_ids:
        parent_obj = scene.object(ap.parent)
        if not parent_obj.pose:
            raise Arcor2Exception("Parent object does not have pose!")
        old_parent_pose = parent_obj.pose
    elif ap.parent in project.action_points_ids:
        old_parent_pose = Pose(project.action_point(ap.parent).position, Orientation())
    else:
        raise Arcor2Exception("AP has unknown parent_id.")

    ap.position = make_pose_abs(old_parent_pose, Pose(ap.position, Orientation())).position
    for ori in ap.orientations:
        ori.orientation = make_orientation_abs(old_parent_pose.orientation, ori.orientation)

    if ap.parent in project.action_points_ids:
        parent_ap = project.action_point(ap.parent)
        if parent_ap.parent:
            ap.parent = parent_ap.parent
            make_relative_ap_global(scene, project, ap)

    ap.parent = None


def make_global_ap_relative(scene: CachedScene, project: CachedProject, ap: ProjectActionPoint, parent_id: str) -> None:
    """
    Transforms (in place) global AP into a relative one with given parent (can be object or another AP).
    :param scene:
    :param project:
    :param ap:
    :param parent_id:
    :return:
    """

    assert project.scene_id == scene.id

    if parent_id in scene.object_ids:
        parent_obj = scene.object(parent_id)
        if not parent_obj.pose:
            raise Arcor2Exception("Parent object does not have pose!")
        new_parent_pose = parent_obj.pose
    elif parent_id in project.action_points_ids:

        parent_ap = project.action_point(parent_id)

        if parent_ap.parent:
            make_global_ap_relative(scene, project, ap, parent_ap.parent)

        new_parent_pose = Pose(parent_ap.position, Orientation())

    else:
        raise Arcor2Exception("Unknown parent_id.")

    ap.position = make_pose_rel(new_parent_pose, Pose(ap.position, Orientation())).position
    for ori in ap.orientations:
        ori.orientation = make_orientation_rel(new_parent_pose.orientation, ori.orientation)

    ap.parent = parent_id


def make_pose_rel_to_parent(scene: CachedScene, project: CachedProject, pose: Pose, parent_id: str) -> Pose:
    """
    Transforms global Pose into Pose that is relative to a given parent (can be object or AP).
    :param scene:
    :param project:
    :param pose:
    :param parent_id:
    :return:
    """

    if parent_id in scene.object_ids:
        parent_obj = scene.object(parent_id)
        if not parent_obj.pose:
            raise Arcor2Exception("Parent object does not have pose!")
        parent_pose = parent_obj.pose
    elif parent_id in project.action_points_ids:

        parent_ap = project.action_point(parent_id)

        if parent_ap.parent:
            pose = make_pose_rel_to_parent(scene, project, pose, parent_ap.parent)

        parent_pose = Pose(parent_ap.position, Orientation())

    else:
        raise Arcor2Exception("Unknown parent_id.")

    return make_pose_rel(parent_pose, pose)
