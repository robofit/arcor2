import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Set, Tuple, ValuesView

from arcor2.data import common as cmn
from arcor2.exceptions import Arcor2Exception

if __debug__:
    import random

# TODO cached ProjectFunction (actions from functions are totally ignored at the moment)


class CachedSceneException(Arcor2Exception):
    pass


class CachedScene:
    def __init__(self, scene: cmn.Scene):

        self.id: str = scene.id
        self.name: str = scene.name
        self.desc: str = scene.desc
        self.modified: Optional[datetime] = scene.modified
        self.int_modified: Optional[datetime] = scene.int_modified

        # TODO deal with children
        self._objects: Dict[str, cmn.SceneObject] = {}

        for obj in scene.objects:

            if obj.id in self._objects:
                raise CachedSceneException(f"Duplicate object id: {obj.id}.")

            self._objects[obj.id] = obj

    @property
    def bare(self) -> cmn.BareScene:
        return cmn.BareScene(self.name, self.desc, self.modified, self.int_modified, id=self.id)

    def object_names(self) -> Iterator[str]:

        for obj in self._objects.values():
            yield obj.name

    @property
    def objects(self) -> Iterator[cmn.SceneObject]:

        for obj in self._objects.values():
            yield obj

    @property
    def object_ids(self) -> Set[str]:
        return set(self._objects.keys())

    def object(self, object_id: str) -> cmn.SceneObject:

        try:
            return self._objects[object_id]
        except KeyError:
            raise Arcor2Exception(f"Object ID {object_id} not found.")

    def objects_of_type(self, obj_type: str) -> Iterator[cmn.SceneObject]:

        for obj in self.objects:
            if obj.type == obj_type:
                yield obj

    @property
    def object_types(self) -> Set[str]:
        return {obj.type for obj in self.objects}

    @property
    def scene(self) -> cmn.Scene:

        sc = cmn.Scene.from_bare(self.bare)
        sc.modified = self.modified
        sc.int_modified = self.int_modified
        sc.objects = list(self.objects)
        return sc


class UpdateableCachedScene(CachedScene):
    def __init__(self, scene: cmn.Scene):
        super(UpdateableCachedScene, self).__init__(copy.deepcopy(scene))

    def update_modified(self) -> None:
        self.int_modified = datetime.now(tz=timezone.utc)

    def has_changes(self) -> bool:

        if self.int_modified is None:
            return False

        if self.modified is None:
            return True

        return self.int_modified > self.modified

    def upsert_object(self, obj: cmn.SceneObject) -> None:

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

    data: Dict[str, cmn.Action] = field(default_factory=dict)
    parent: Dict[str, cmn.BareActionPoint] = field(default_factory=dict)


@dataclass
class Joints:

    data: Dict[str, cmn.ProjectRobotJoints] = field(default_factory=dict)
    parent: Dict[str, cmn.BareActionPoint] = field(default_factory=dict)


@dataclass
class Orientations:

    data: Dict[str, cmn.NamedOrientation] = field(default_factory=dict)
    parent: Dict[str, cmn.BareActionPoint] = field(default_factory=dict)


class CachedProject:
    def __init__(self, project: cmn.Project):

        self.id: str = project.id
        self.name: str = project.name
        self.scene_id: str = project.scene_id
        self.desc: str = project.desc
        self.has_logic: bool = project.has_logic
        self.modified: Optional[datetime] = project.modified
        self._int_modified: Optional[datetime] = project.int_modified

        self._action_points: Dict[str, cmn.BareActionPoint] = {}

        self._actions = Actions()
        self._joints = Joints()
        self._orientations = Orientations()

        self._constants: Dict[str, cmn.ProjectConstant] = {}
        self._logic_items: Dict[str, cmn.LogicItem] = {}
        self._functions: Dict[str, cmn.ProjectFunction] = {}

        self.overrides: Dict[str, List[cmn.Parameter]] = {}

        for ap in project.action_points:

            if ap.id in self._action_points:
                raise CachedProjectException(f"Duplicate AP id: {ap.id}.")

            bare_ap = cmn.BareActionPoint(ap.name, ap.position, ap.parent, id=ap.id)
            self._action_points[ap.id] = bare_ap

            for ac in ap.actions:

                if ac.id in self._actions.data:
                    raise CachedProjectException(f"Duplicate action id: {ac.id}.")

                self._actions.data[ac.id] = ac
                self._actions.parent[ac.id] = bare_ap

            for joints in ap.robot_joints:

                if joints.id in self._joints.data:
                    raise CachedProjectException(f"Duplicate joints id: {joints.id}.")

                self._joints.data[joints.id] = joints
                self._joints.parent[joints.id] = bare_ap

            for orientation in ap.orientations:

                if orientation.id in self._orientations.data:
                    raise CachedProjectException(f"Duplicate orientation id: {orientation.id}.")

                self._orientations.data[orientation.id] = orientation
                self._orientations.parent[orientation.id] = bare_ap

        for override in project.object_overrides:
            self.overrides[override.id] = override.parameters

        for constant in project.constants:
            self._constants[constant.id] = constant

        for logic_item in project.logic:
            self._logic_items[logic_item.id] = logic_item

        for function in project.functions:
            self._functions[function.id] = function

    @property
    def logic(self) -> ValuesView[cmn.LogicItem]:
        return self._logic_items.values()

    @property
    def valid_logic_endpoints(self) -> Set[str]:
        return {cmn.LogicItem.START, cmn.LogicItem.END} | self._logic_items.keys()

    @property
    def constants(self) -> ValuesView[cmn.ProjectConstant]:
        return self._constants.values()

    @property
    def functions(self) -> ValuesView[cmn.ProjectFunction]:
        return self._functions.values()

    @property
    def project(self) -> cmn.Project:

        proj = cmn.Project.from_bare(self.bare)

        for bare_ap in self._action_points.values():

            ap = cmn.ActionPoint.from_bare(bare_ap)
            ap.actions = self.ap_actions(ap.id)
            ap.robot_joints = self.ap_joints(ap.id)
            ap.orientations = self.ap_orientations(ap.id)
            proj.action_points.append(ap)

        proj.object_overrides = [cmn.SceneObjectOverride(k, v) for k, v in self.overrides.items()]
        proj.constants = list(self.constants)
        proj.functions = list(self.functions)
        proj.logic = list(self.logic)
        return proj

    @property
    def bare(self) -> cmn.BareProject:
        return cmn.BareProject(self.name, self.scene_id, self.desc, self.has_logic, id=self.id)

    @property
    def action_points(self) -> ValuesView[cmn.BareActionPoint]:
        return self._action_points.values()

    @property
    def action_points_with_parent(self) -> List[cmn.BareActionPoint]:
        """Get action points which are relative to something (parent is set).

        :return:
        """

        return [ap for ap in self._action_points.values() if ap.parent]

    @property
    def action_names(self) -> Set[str]:
        return {act.name for act in self._actions.data.values()}

    @property
    def action_points_names(self) -> Set[str]:
        return {ap.name for ap in self._action_points.values()}

    @property
    def action_points_ids(self) -> Set[str]:
        return set(self._action_points.keys())

    def ap_and_joints(self, joints_id: str) -> Tuple[cmn.BareActionPoint, cmn.ProjectRobotJoints]:

        try:
            return self._joints.parent[joints_id], self._joints.data[joints_id]
        except KeyError:
            raise CachedProjectException("Unknown joints.")

    def joints(self, joints_id: str) -> cmn.ProjectRobotJoints:

        try:
            return self._joints.data[joints_id]
        except KeyError:
            raise CachedProjectException("Unknown joints.")

    def bare_ap_and_orientation(self, orientation_id: str) -> Tuple[cmn.BareActionPoint, cmn.NamedOrientation]:

        try:
            return self._orientations.parent[orientation_id], self._orientations.data[orientation_id]
        except KeyError:
            raise CachedProjectException("Unknown orientation.")

    def pose(self, orientation_id: str) -> cmn.Pose:

        ap, ori = self.bare_ap_and_orientation(orientation_id)
        return cmn.Pose(ap.position, ori.orientation)

    def ap_orientations(self, ap_id: str) -> List[cmn.NamedOrientation]:

        # TODO come up with something more efficient
        return [
            self._orientations.data[ori_id]
            for ori_id, parent_ap in self._orientations.parent.items()
            if ap_id == parent_ap.id
        ]

    def ap_joints(self, ap_id: str) -> List[cmn.ProjectRobotJoints]:

        # TODO come up with something more efficient
        return [
            self._joints.data[joints_id]
            for joints_id, parent_ap in self._joints.parent.items()
            if ap_id == parent_ap.id
        ]

    def ap_actions(self, ap_id: str) -> List[cmn.Action]:

        # TODO come up with something more efficient
        return [
            self._actions.data[action_id]
            for action_id, parent_ap in self._actions.parent.items()
            if ap_id == parent_ap.id
        ]

    def ap_action_ids(self, ap_id: str) -> Set[str]:
        return {ac.id for ac in self.ap_actions(ap_id)}

    def ap_orientation_names(self, ap_id: str) -> Set[str]:
        return {ori.name for ori in self.ap_orientations(ap_id)}

    def ap_joint_names(self, ap_id: str) -> Set[str]:
        return {joints.name for joints in self.ap_joints(ap_id)}

    def ap_action_names(self, ap_id: str) -> Set[str]:
        return {action.name for action in self.ap_actions(ap_id)}

    def orientation(self, orientation_id: str) -> cmn.NamedOrientation:

        try:
            return self._orientations.data[orientation_id]
        except KeyError:
            raise CachedProjectException("Unknown orientation.")

    def action(self, action_id: str) -> cmn.Action:

        try:
            return self._actions.data[action_id]
        except KeyError:
            raise CachedProjectException("Action not found")

    def action_io(self, action_id: str) -> Tuple[List[cmn.LogicItem], List[cmn.LogicItem]]:
        """Returns list of logical connection ending in the action (its inputs)
        and starting from the action (its outputs)

        :param action_id:
        :return:
        """

        inputs: List[cmn.LogicItem] = []
        outputs: List[cmn.LogicItem] = []

        for item in self._logic_items.values():
            parsed_start = item.parse_start()
            if parsed_start.start_action_id == action_id:
                outputs.append(item)
            if item.end == action_id:
                inputs.append(item)

        if __debug__:  # make it a bit harder for tests to succeed
            random.shuffle(inputs)
            random.shuffle(outputs)

        return inputs, outputs

    def first_action_id(self) -> str:

        first_action: Optional[str] = None

        for item in self._logic_items.values():
            if item.start == item.START:
                if first_action:
                    raise CachedProjectException("Duplicate start.")
                first_action = self.action(item.end).id

        if first_action is None:
            raise CachedProjectException("Start action not found.")

        return first_action

    def action_point_and_action(self, action_id: str) -> Tuple[cmn.BareActionPoint, cmn.Action]:

        try:
            return self._actions.parent[action_id], self._actions.data[action_id]
        except KeyError:
            raise CachedProjectException("Action not found")

    @property
    def actions(self) -> List[cmn.Action]:
        return list(self._actions.data.values())

    def action_ids(self) -> Set[str]:
        return {action.id for action in self._actions.data.values()}

    def bare_action_point(self, action_point_id: str) -> cmn.BareActionPoint:

        try:
            return self._action_points[action_point_id]
        except KeyError:
            raise CachedProjectException("Action point not found")

    def action_point(self, action_point_id: str) -> cmn.ActionPoint:

        ap = cmn.ActionPoint.from_bare(self.bare_action_point(action_point_id))
        ap.orientations = self.ap_orientations(action_point_id)
        ap.robot_joints = self.ap_joints(action_point_id)
        return ap

    def logic_item(self, logic_item_id: str) -> cmn.LogicItem:

        try:
            return self._logic_items[logic_item_id]
        except KeyError:
            raise CachedProjectException("LogicItem not found.")

    def constant(self, constant_id: str) -> cmn.ProjectConstant:

        try:
            return self._constants[constant_id]
        except KeyError:
            raise CachedProjectException("Constant not found.")


class UpdateableCachedProject(CachedProject):
    def __init__(self, project: cmn.Project):
        super(UpdateableCachedProject, self).__init__(copy.deepcopy(project))

    def update_modified(self) -> None:
        self._int_modified = datetime.now(tz=timezone.utc)

    @property
    def has_changes(self) -> bool:

        if self._int_modified is None:
            return False

        if self.modified is None:
            return True

        return self._int_modified > self.modified

    def upsert_action(self, ap_id: str, action: cmn.Action) -> None:

        ap = self.bare_action_point(ap_id)

        if action.id in self._actions.data:
            assert self._actions.parent[action.id] == ap
            self._actions.data[action.id] = action
        else:
            self._actions.data[action.id] = action
            self._actions.parent[action.id] = ap
        self.update_modified()

    def remove_action(self, action_id: str) -> cmn.Action:

        try:
            action = self._actions.data.pop(action_id)
            del self._actions.parent[action_id]  # TODO KeyError here might be probably ignored? (it should not happen)
        except KeyError as e:
            raise CachedProjectException("Action not found.") from e
        self.update_modified()
        return action

    def invalidate_joints(self, ap_id: str) -> None:

        for joints in self.ap_joints(ap_id):
            joints.is_valid = False

    def update_ap_position(self, ap_id: str, position: cmn.Position) -> None:

        ap = self.bare_action_point(ap_id)
        ap.position = position
        self.invalidate_joints(ap_id)
        self.update_modified()

    def upsert_orientation(self, ap_id: str, orientation: cmn.NamedOrientation) -> None:

        ap = self.bare_action_point(ap_id)

        if orientation.id in self._orientations.data:
            assert self._orientations.parent[orientation.id] == ap
            self._orientations.data[orientation.id] = orientation
        else:
            self._orientations.data[orientation.id] = orientation
            self._orientations.parent[orientation.id] = ap
        self.update_modified()

    def remove_orientation(self, orientation_id: str) -> cmn.NamedOrientation:

        try:
            ori = self._orientations.data.pop(orientation_id)
            del self._orientations.parent[orientation_id]
        except KeyError as e:
            raise CachedProjectException("Orientation not found.") from e
        self.update_modified()
        return ori

    def upsert_joints(self, ap_id: str, joints: cmn.ProjectRobotJoints) -> None:

        ap = self.bare_action_point(ap_id)

        if joints.id in self._joints.data:
            assert self._joints.parent[joints.id] == ap
            self._joints.data[joints.id] = joints
        else:
            self._joints.data[joints.id] = joints
            self._joints.parent[joints.id] = ap
        self.update_modified()

    def remove_joints(self, joints_id: str) -> cmn.ProjectRobotJoints:

        try:
            joints = self._joints.data.pop(joints_id)
            del self._joints.parent[joints_id]
        except KeyError as e:
            raise CachedProjectException("Joints not found.") from e
        self.update_modified()
        return joints

    def upsert_action_point(
        self, ap_id: str, name: str, position: cmn.Position, parent: Optional[str] = None
    ) -> cmn.BareActionPoint:

        try:
            ap = self.bare_action_point(ap_id)
            ap.name = name
            if position != ap.position:
                self.invalidate_joints(ap_id)
            ap.position = position
            ap.parent = parent
        except CachedProjectException:
            ap = cmn.BareActionPoint(name, position, parent, id=ap_id)
            self._action_points[ap_id] = ap
        self.update_modified()
        return ap

    def remove_action_point(self, ap_id: str) -> cmn.BareActionPoint:

        ap = self.bare_action_point(ap_id)

        for action in self.ap_actions(ap_id):
            self.remove_action(action.id)

        for joints in self.ap_joints(ap_id):
            self.remove_joints(joints.id)

        for ori in self.ap_orientations(ap_id):
            self.remove_orientation(ori.id)

        del self._action_points[ap_id]
        self.update_modified()
        return ap

    def upsert_logic_item(self, logic_item: cmn.LogicItem) -> None:

        self._logic_items[logic_item.id] = logic_item
        self.update_modified()

    def remove_logic_item(self, logic_item_id: str) -> cmn.LogicItem:

        try:
            logic_item = self._logic_items.pop(logic_item_id)
        except KeyError as e:
            raise CachedProjectException("Logic item not found.") from e
        self.update_modified()
        return logic_item

    def clear_logic(self) -> None:

        self._logic_items.clear()
        self.update_modified()

    def upsert_constant(self, const: cmn.ProjectConstant) -> None:
        self._constants[const.id] = const
        self.update_modified()

    def remove_constant(self, const_id: str) -> cmn.ProjectConstant:

        try:
            const = self._constants.pop(const_id)
        except KeyError as e:
            raise CachedProjectException("Constant not found.") from e
        self.update_modified()
        return const
