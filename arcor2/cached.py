from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Set, Tuple, ValuesView

from arcor2.data.common import Action, LogicItem, NamedOrientation, Pose, Position, Project, ProjectActionPoint,\
    ProjectConstant, ProjectFunction, ProjectRobotJoints, Scene, SceneObject
from arcor2.exceptions import Arcor2Exception

# TODO cached ProjectFunction (actions from functions are totally ignored at the moment)


class CachedSceneException(Arcor2Exception):
    pass


class CachedScene:

    def __init__(self, scene: Scene):

        self.id: str = scene.id
        self.name: str = scene.name
        self.desc: str = scene.desc
        self.modified: Optional[datetime] = scene.modified
        self.int_modified: Optional[datetime] = scene.int_modified

        # TODO deal with children
        self._objects: Dict[str, SceneObject] = {}

        for obj in scene.objects:

            if obj.id in self._objects:
                raise CachedSceneException(f"Duplicate object id: {obj.id}.")

            self._objects[obj.id] = obj

    @property
    def bare(self) -> Scene:
        return Scene(self.id, self.name, desc=self.desc)

    def object_names(self) -> Iterator[str]:

        for obj in self._objects.values():
            yield obj.name

    @property
    def objects(self) -> Iterator[SceneObject]:

        for obj in self._objects.values():
            yield obj

    @property
    def object_ids(self) -> Set[str]:
        return set(self._objects.keys())

    def object(self, object_id: str) -> SceneObject:

        try:
            return self._objects[object_id]
        except KeyError:
            raise Arcor2Exception(f"Object ID {object_id} not found.")

    def objects_of_type(self, obj_type: str) -> Iterator[SceneObject]:

        for obj in self.objects:
            if obj.type == obj_type:
                yield obj

    @property
    def scene(self) -> Scene:

        sc = self.bare
        sc.modified = self.modified
        sc.int_modified = self.int_modified
        sc.objects = list(self.objects)
        return sc


class UpdateableCachedScene(CachedScene):

    def update_modified(self) -> None:
        self.int_modified = datetime.now(tz=timezone.utc)

    def has_changes(self) -> bool:

        if self.int_modified is None:
            return False

        if self.modified is None:
            return True

        return self.int_modified > self.modified

    def upsert_object(self, obj: SceneObject) -> None:

        self._objects[obj.id] = obj
        self.update_modified()

    def delete_object(self, obj_id: str) -> None:

        try:
            del self._objects[obj_id]
        except KeyError as e:
            raise Arcor2Exception("Object id not found.") from e

        self.update_modified()


class CachedProjectException(Arcor2Exception):
    pass


@dataclass
class Actions:

    data: Dict[str, Action] = field(default_factory=dict)
    parent: Dict[str, ProjectActionPoint] = field(default_factory=dict)


@dataclass
class Joints:

    data: Dict[str, ProjectRobotJoints] = field(default_factory=dict)
    parent: Dict[str, ProjectActionPoint] = field(default_factory=dict)


@dataclass
class Orientations:

    data: Dict[str, NamedOrientation] = field(default_factory=dict)
    parent: Dict[str, ProjectActionPoint] = field(default_factory=dict)


class CachedProject:

    def __init__(self, project: Project):

        project_copy = deepcopy(project)  # do not modify original project

        self.id: str = project_copy.id
        self.name: str = project_copy.name
        self.scene_id: str = project_copy.scene_id
        self.desc: str = project_copy.desc
        self.has_logic: bool = project_copy.has_logic
        self.modified: Optional[datetime] = project_copy.modified
        self._int_modified: Optional[datetime] = project_copy.int_modified

        self._action_points: Dict[str, ProjectActionPoint] = {}

        self._actions = Actions()
        self._joints = Joints()
        self._orientations = Orientations()

        self._constants: Dict[str, ProjectConstant] = {}
        self._logic_items: Dict[str, LogicItem] = {}
        self._functions: Dict[str, ProjectFunction] = {}

        for ap in project_copy.action_points:

            if ap.id in self._action_points:
                raise CachedProjectException(f"Duplicate AP id: {ap.id}.")

            self._action_points[ap.id] = ap

            for ac in ap.actions:

                if ac.id in self._actions.data:
                    raise CachedProjectException(f"Duplicate action id: {ac.id}.")

                self._actions.data[ac.id] = ac
                self._actions.parent[ac.id] = ap

            for joints in ap.robot_joints:

                if joints.id in self._joints.data:
                    raise CachedProjectException(f"Duplicate joints id: {joints.id}.")

                self._joints.data[joints.id] = joints
                self._joints.parent[joints.id] = ap

            for orientation in ap.orientations:

                if orientation.id in self._orientations.data:
                    raise CachedProjectException(f"Duplicate orientation id: {orientation.id}.")

                self._orientations.data[orientation.id] = orientation
                self._orientations.parent[orientation.id] = ap

            ap.actions.clear()
            ap.robot_joints.clear()
            ap.orientations.clear()

        for constant in project_copy.constants:
            self._constants[constant.id] = constant

        for logic_item in project_copy.logic:
            self._logic_items[logic_item.id] = logic_item

        for function in project_copy.functions:
            self._functions[function.id] = function

    @property
    def logic(self) -> ValuesView[LogicItem]:
        return self._logic_items.values()

    @property
    def constants(self) -> ValuesView[ProjectConstant]:
        return self._constants.values()

    @property
    def functions(self) -> ValuesView[ProjectFunction]:
        return self._functions.values()

    @property
    def project(self) -> Project:

        proj = Project(self.id, self.name, self.scene_id, self.desc, self.has_logic, self.modified, self._int_modified)

        proj.action_points = list(self._action_points.values())

        for ap in proj.action_points:

            ap.actions.clear()
            ap.robot_joints.clear()
            ap.orientations.clear()

            for act_id, parent_ap in self._actions.parent.items():
                if ap == parent_ap:
                    ap.actions.append(self._actions.data[act_id])

            for joints_id, parent_ap in self._joints.parent.items():
                if ap == parent_ap:
                    ap.robot_joints.append(self._joints.data[joints_id])

            for ori_id, parent_ap in self._orientations.parent.items():
                if ap == parent_ap:
                    ap.orientations.append(self._orientations.data[ori_id])

        proj.constants = list(self.constants)
        proj.functions = list(self.functions)
        proj.logic = list(self.logic)
        return proj

    @property
    def bare(self) -> Project:
        return Project(self.id, self.name, self.scene_id, self.desc, self.has_logic)

    @property
    def action_points(self) -> ValuesView[ProjectActionPoint]:
        return self._action_points.values()

    @property
    def action_points_with_parent(self) -> List[ProjectActionPoint]:
        """
        Get action points which are relative to something (parent is set).
        :return:
        """

        return [ap for ap in self._action_points.values() if ap.parent]

    @property
    def action_points_names(self) -> Set[str]:
        return {ap.name for ap in self._action_points.values()}

    @property
    def action_points_ids(self) -> Set[str]:
        return set(self._action_points.keys())

    def ap_and_joints(self, joints_id: str) -> Tuple[ProjectActionPoint, ProjectRobotJoints]:

        try:
            return self._joints.parent[joints_id], self._joints.data[joints_id]
        except KeyError:
            raise CachedProjectException("Unknown joints.")

    def joints(self, joints_id: str) -> ProjectRobotJoints:

        try:
            return self._joints.data[joints_id]
        except KeyError:
            raise CachedProjectException("Unknown joints.")

    def ap_and_orientation(self, orientation_id: str) -> Tuple[ProjectActionPoint, NamedOrientation]:

        try:
            return self._orientations.parent[orientation_id], self._orientations.data[orientation_id]
        except KeyError:
            raise CachedProjectException("Unknown orientation.")

    def orientation(self, orientation_id: str) -> NamedOrientation:

        try:
            return self._orientations.data[orientation_id]
        except KeyError:
            raise CachedProjectException("Unknown orientation.")

    def pose(self, orientation_id: str) -> Pose:

        ap, ori = self.ap_and_orientation(orientation_id)
        return Pose(ap.position, ori.orientation)

    def action(self, action_id: str) -> Action:

        try:
            return self._actions.data[action_id]
        except KeyError:
            raise CachedProjectException("Action not found")

    def action_point_and_action(self, action_id: str) -> Tuple[ProjectActionPoint, Action]:

        try:
            return self._actions.parent[action_id], self._actions.data[action_id]
        except KeyError:
            raise CachedProjectException("Action not found")

    @property
    def actions(self) -> List[Action]:
        return list(self._actions.data.values())

    def action_ids(self) -> Set[str]:
        return {action.id for action in self.actions}

    def action_user_names(self) -> Set[str]:
        return {action.name for action in self.actions}

    def action_point(self, action_point_id: str) -> ProjectActionPoint:

        try:
            return self._action_points[action_point_id]
        except KeyError:
            raise CachedProjectException("Action point not found")

    def logic_item(self, logic_item_id: str) -> LogicItem:

        try:
            return self._logic_items[logic_item_id]
        except KeyError:
            raise CachedProjectException("LogicItem not found.")

    def constant(self, constant_id: str) -> ProjectConstant:

        try:
            return self._constants[constant_id]
        except KeyError:
            raise CachedProjectException("Constant not found.")


class UpdateableCachedProject(CachedProject):

    def update_modified(self) -> None:
        self._int_modified = datetime.now(tz=timezone.utc)

    @property
    def has_changes(self) -> bool:

        if self._int_modified is None:
            return False

        if self.modified is None:
            return True

        return self._int_modified > self.modified

    def upsert_action(self, ap_id: str, action: Action) -> None:

        ap = self.action_point(ap_id)

        if action.id in self._actions.data:
            assert self._actions.parent[action.id] == ap
            self._actions.data[action.id] = action
        else:
            self._actions.data[action.id] = action
            self._actions.parent[action.id] = ap
        self.update_modified()

    def remove_action(self, action_id: str) -> Action:

        try:
            action = self._actions.data.pop(action_id)
            del self._actions.parent[action_id]  # TODO KeyError here might be probably ignored? (it should not happen)
        except KeyError as e:
            raise CachedProjectException("Action not found.") from e
        self.update_modified()
        return action

    def upsert_orientation(self, ap_id: str, orientation: NamedOrientation) -> None:

        ap = self.action_point(ap_id)

        if orientation.id in self._orientations.data:
            assert self._orientations.parent[orientation.id] == ap
            self._orientations.data[orientation.id] = orientation
        else:
            self._orientations.data[orientation.id] = orientation
            self._orientations.parent[orientation.id] = ap
        self.update_modified()

    def remove_orientation(self, orientation_id: str) -> NamedOrientation:

        try:
            ori = self._orientations.data.pop(orientation_id)
            del self._orientations.parent[orientation_id]
        except KeyError as e:
            raise CachedProjectException("Orientation not found.") from e
        self.update_modified()
        return ori

    def upsert_joints(self, ap_id: str, joints: ProjectRobotJoints) -> None:

        ap = self.action_point(ap_id)

        if joints.id in self._joints.data:
            assert self._joints.parent[joints.id] == ap
            self._joints.data[joints.id] = joints
        else:
            self._joints.data[joints.id] = joints
            self._joints.parent[joints.id] = ap
        self.update_modified()

    def remove_joints(self, joints_id: str) -> ProjectRobotJoints:

        try:
            joints = self._joints.data.pop(joints_id)
            del self._joints.parent[joints_id]
        except KeyError as e:
            raise CachedProjectException("Joints not found.") from e
        self.update_modified()
        return joints

    def upsert_action_point(self, ap_id: str, name: str, position: Position, parent: Optional[str] = None) \
            -> ProjectActionPoint:

        try:
            ap = self.action_point(ap_id)
            ap.name = name
            ap.position = position
            ap.parent = parent
        except CachedProjectException:
            ap = ProjectActionPoint(ap_id, name, position, parent)
            self._action_points[ap_id] = ap
        self.update_modified()
        return ap

    def remove_action_point(self, ap_id: str) -> ProjectActionPoint:

        ap = self.action_point(ap_id)

        for action in ap.actions:
            self.remove_action(action.id)
        for joints in ap.robot_joints:
            self.remove_joints(joints.id)
        for ori in ap.orientations:
            self.remove_orientation(ori.id)

        del self._action_points[ap_id]
        self.update_modified()
        return ap

    def upsert_logic_item(self, logic_item: LogicItem) -> None:
        self._logic_items[logic_item.id] = logic_item
        self.update_modified()

    def remove_logic_item(self, logic_item_id: str) -> LogicItem:

        try:
            logic_item = self._logic_items.pop(logic_item_id)
        except KeyError as e:
            raise CachedProjectException("Logic item not found.") from e
        self.update_modified()
        return logic_item

    def clear_logic(self) -> None:

        self._logic_items.clear()
        self.update_modified()

    def upsert_constant(self, const: ProjectConstant) -> None:
        self._constants[const.id] = const
        self.update_modified()

    def remove_constant(self, const_id: str) -> ProjectConstant:

        try:
            const = self._constants.pop(const_id)
        except KeyError as e:
            raise CachedProjectException("Constant not found.") from e
        self.update_modified()
        return const
