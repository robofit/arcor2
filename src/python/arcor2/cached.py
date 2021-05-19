import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Set, Tuple, Union, ValuesView

from arcor2.data import common as cmn
from arcor2.exceptions import Arcor2Exception

if __debug__:
    import random

# TODO cached ProjectFunction (actions from functions are totally ignored at the moment)


class CachedSceneException(Arcor2Exception):
    pass


class CachedBase:
    def __init__(self, data: Union[cmn.Scene, cmn.Project]) -> None:

        self.id: str = data.id
        self.name: str = data.name
        self.description: str = data.description

        self.created: Optional[datetime] = data.created
        self.modified: Optional[datetime] = data.modified
        self._int_modified: Optional[datetime] = data.int_modified


class UpdateableMixin:

    if TYPE_CHECKING:
        modified: Optional[datetime] = None
        _int_modified: Optional[datetime] = None

    def update_modified(self) -> None:
        self._int_modified = datetime.now(tz=timezone.utc)

    @property
    def has_changes(self) -> bool:
        """Returns whether the scene/project has some unsaved changes.

        :return:
        """

        # this is true for a newly created scene/project
        # it does not matter if there are changes or not - the scene/project was not saved yet
        if self.modified is None:
            return True

        # this is true for scene/project that was loaded but there are not changes yet
        if self._int_modified is None:
            return False

        # if the scene/project was already saved once (modified is not None)
        # and there were some changes (int_modified is not None)
        # let's compare if some change happened (int_modified) after saving to the Project service (modified)
        return self._int_modified > self.modified


class CachedScene(CachedBase):
    def __init__(self, scene: cmn.Scene) -> None:

        super().__init__(scene)

        # TODO deal with children
        self._objects: Dict[str, cmn.SceneObject] = {}

        for obj in scene.objects:

            if obj.id in self._objects:
                raise CachedSceneException(f"Duplicate object id: {obj.id}.")

            self._objects[obj.id] = obj

    @property
    def bare(self) -> cmn.BareScene:
        return cmn.BareScene(self.name, self.description, self.created, self.modified, self._int_modified, id=self.id)

    def object_names(self) -> Iterator[str]:

        for obj in self._objects.values():
            yield obj.name

    @property
    def objects(self) -> Iterator[cmn.SceneObject]:

        for obj in self._objects.values():
            yield obj

    @property
    def object_ids(self) -> Set[str]:
        return set(self._objects)

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
        sc.int_modified = self._int_modified
        sc.objects = list(self.objects)
        return sc


class UpdateableCachedScene(UpdateableMixin, CachedScene):
    def __init__(self, scene: cmn.Scene):
        super(UpdateableCachedScene, self).__init__(copy.deepcopy(scene))

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
class Parent:
    ap: cmn.BareActionPoint


@dataclass
class ApAction(Parent):
    action: cmn.Action


@dataclass
class ApJoints(Parent):
    joints: cmn.ProjectRobotJoints


@dataclass
class ApOrientation(Parent):
    orientation: cmn.NamedOrientation


class CachedProject(CachedBase):
    def __init__(self, project: cmn.Project):

        super().__init__(project)

        self.scene_id: str = project.scene_id
        self.has_logic: bool = project.has_logic

        self._action_points: Dict[str, cmn.BareActionPoint] = {}

        self._actions: Dict[str, ApAction] = {}
        self._joints: Dict[str, ApJoints] = {}
        self._orientations: Dict[str, ApOrientation] = {}

        self._constants: Dict[str, cmn.ProjectConstant] = {}
        self._logic_items: Dict[str, cmn.LogicItem] = {}
        self._functions: Dict[str, cmn.ProjectFunction] = {}

        self.overrides: Dict[str, List[cmn.Parameter]] = {}

        self._childs: Dict[str, Set[str]] = {}

        for ap in project.action_points:

            if ap.id in self._action_points:
                raise CachedProjectException(f"Duplicate AP id: {ap.id}.")

            bare_ap = cmn.BareActionPoint(ap.name, ap.position, ap.parent, id=ap.id)
            self._action_points[ap.id] = bare_ap
            self._upsert_child(ap.parent, ap.id)

            for ac in ap.actions:

                if ac.id in self._actions:
                    raise CachedProjectException(f"Duplicate action id: {ac.id}.")

                self._actions[ac.id] = ApAction(bare_ap, ac)
                self._upsert_child(ap.id, ac.id)

            for joints in ap.robot_joints:

                if joints.id in self._joints:
                    raise CachedProjectException(f"Duplicate joints id: {joints.id}.")

                self._joints[joints.id] = ApJoints(bare_ap, joints)
                self._upsert_child(ap.id, joints.id)

            for orientation in ap.orientations:

                if orientation.id in self._orientations:
                    raise CachedProjectException(f"Duplicate orientation id: {orientation.id}.")

                self._orientations[orientation.id] = ApOrientation(bare_ap, orientation)
                self._upsert_child(ap.id, orientation.id)

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
        return cmn.BareProject(
            self.name,
            self.scene_id,
            self.description,
            self.has_logic,
            self.created,
            self.modified,
            self._int_modified,
            id=self.id,
        )

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
        return {value.action.name for value in self._actions.values()}

    @property
    def action_points_names(self) -> Set[str]:
        return {ap.name for ap in self._action_points.values()}

    @property
    def action_points_ids(self) -> Set[str]:
        return set(self._action_points)

    def ap_and_joints(self, joints_id: str) -> Tuple[cmn.BareActionPoint, cmn.ProjectRobotJoints]:

        try:
            value = self._joints[joints_id]
        except KeyError:
            raise CachedProjectException("Unknown joints.")

        return value.ap, value.joints

    def joints(self, joints_id: str) -> cmn.ProjectRobotJoints:

        try:
            return self._joints[joints_id].joints
        except KeyError:
            raise CachedProjectException("Unknown joints.")

    def bare_ap_and_orientation(self, orientation_id: str) -> Tuple[cmn.BareActionPoint, cmn.NamedOrientation]:

        try:
            value = self._orientations[orientation_id]
        except KeyError:
            raise CachedProjectException("Unknown orientation.")

        return value.ap, value.orientation

    def pose(self, orientation_id: str) -> cmn.Pose:

        ap, ori = self.bare_ap_and_orientation(orientation_id)
        return cmn.Pose(ap.position, ori.orientation)

    def ap_orientations(self, ap_id: str) -> List[cmn.NamedOrientation]:

        return [value.orientation for value in self._orientations.values() if ap_id == value.ap.id]

    def ap_joints(self, ap_id: str) -> List[cmn.ProjectRobotJoints]:

        return [value.joints for value in self._joints.values() if ap_id == value.ap.id]

    def ap_actions(self, ap_id: str) -> List[cmn.Action]:

        return [value.action for value in self._actions.values() if ap_id == value.ap.id]

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
            return self._orientations[orientation_id].orientation
        except KeyError:
            raise CachedProjectException("Unknown orientation.")

    def action(self, action_id: str) -> cmn.Action:

        try:
            return self._actions[action_id].action
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
            value = self._actions[action_id]
        except KeyError:
            raise CachedProjectException("Action not found")

        return value.ap, value.action

    @property
    def actions(self) -> List[cmn.Action]:
        return [value.action for value in self._actions.values()]

    def action_ids(self) -> Set[str]:
        return set(self._actions)

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

    def get_by_id(
        self, obj_id: str
    ) -> Union[cmn.BareActionPoint, cmn.NamedOrientation, cmn.ProjectRobotJoints, cmn.Action]:

        if obj_id in self._action_points:  # AP
            return self._action_points[obj_id]
        elif obj_id in self._joints:  # Joints
            return self._joints[obj_id].joints
        elif obj_id in self._orientations:  # Orientation
            return self._orientations[obj_id].orientation
        elif obj_id in self._actions:  # Action
            return self._actions[obj_id].action

        raise CachedProjectException("Object not found.")

    def get_parent_id(self, obj_id: str) -> Optional[str]:

        if obj_id in self._action_points:  # AP
            return self._action_points[obj_id].parent if self._action_points[obj_id].parent else None
        elif obj_id in self._joints:  # Joints
            return self._joints[obj_id].ap.id
        elif obj_id in self._orientations:  # Orientation
            return self._orientations[obj_id].ap.id
        elif obj_id in self._actions:  # Action
            return self._actions[obj_id].ap.id

        raise CachedProjectException("Object not found.")

    def _upsert_child(self, parent: Optional[str], child: str) -> None:
        if parent:
            if parent not in self._childs:
                self._childs[parent] = set()
            self._childs[parent].add(child)

    def childs(self, obj_id: str) -> Set[str]:
        try:
            return self._childs[obj_id]
        except KeyError:
            return set()

    def _remove_child(self, parent: Optional[str], child: str) -> None:

        if parent and parent in self._childs:
            self._childs[parent].remove(child)
            if not self._childs[parent]:
                del self._childs[parent]

    def update_child(self, obj_id: str, old_parent: Optional[str], new_parent: Optional[str]) -> None:

        self._remove_child(old_parent, obj_id)
        self._upsert_child(new_parent, obj_id)


class UpdateableCachedProject(UpdateableMixin, CachedProject):
    def __init__(self, project: cmn.Project):
        super(UpdateableCachedProject, self).__init__(copy.deepcopy(project))

    def upsert_action(self, ap_id: str, action: cmn.Action) -> None:

        ap = self.bare_action_point(ap_id)

        if action.id in self._actions:
            assert self._actions[action.id].ap == ap
            self._actions[action.id].action = action
        else:
            self._actions[action.id] = ApAction(ap, action)

        self._upsert_child(ap.id, action.id)
        self.update_modified()

    def remove_action(self, action_id: str) -> cmn.Action:

        try:
            value = self._actions.pop(action_id)
        except KeyError as e:
            raise CachedProjectException("Action not found.") from e

        self._remove_child(value.ap.id, action_id)
        self.update_modified()
        return value.action

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

        if orientation.id in self._orientations:
            assert self._orientations[orientation.id].ap == ap
            self._orientations[orientation.id].orientation = orientation
        else:
            self._orientations[orientation.id] = ApOrientation(ap, orientation)

        self._upsert_child(ap_id, orientation.id)
        self.update_modified()

    def remove_orientation(self, orientation_id: str) -> cmn.NamedOrientation:

        try:
            value = self._orientations.pop(orientation_id)
        except KeyError as e:
            raise CachedProjectException("Orientation not found.") from e

        self._remove_child(value.ap.id, orientation_id)
        self.update_modified()
        return value.orientation

    def upsert_joints(self, ap_id: str, joints: cmn.ProjectRobotJoints) -> None:

        ap = self.bare_action_point(ap_id)

        if joints.id in self._joints:
            assert self._joints[joints.id].ap == ap
            self._joints[joints.id].joints = joints
        else:
            self._joints[joints.id] = ApJoints(ap, joints)

        self._upsert_child(ap_id, joints.id)
        self.update_modified()

    def remove_joints(self, joints_id: str) -> cmn.ProjectRobotJoints:

        try:
            value = self._joints.pop(joints_id)
        except KeyError as e:
            raise CachedProjectException("Joints not found.") from e

        self._remove_child(value.ap.id, joints_id)
        self.update_modified()
        return value.joints

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
        self._upsert_child(parent, ap_id)
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

        self._remove_child(ap.parent, ap_id)
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
