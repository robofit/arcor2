import concurrent.futures
import importlib
import os
import time
from threading import Event
from types import TracebackType
from typing import Dict, List, Optional, Set, Type, TypeVar

import humps
from arcor2_runtime import action
from arcor2_runtime.action import AP_ID_ATTR, patch_object_actions, patch_with_action_mapping, print_event
from arcor2_runtime.arguments import parse_args
from arcor2_runtime.events import RobotEef, RobotJoints
from arcor2_runtime.exceptions import print_exception
from dataclasses_jsonschema import JsonSchemaMixin, JsonSchemaValidationError

from arcor2 import env, json
from arcor2 import transformations as tr
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import scene_service
from arcor2.data.common import Project, Scene
from arcor2.data.events import PackageInfo
from arcor2.data.object_type import Box, Cylinder, Mesh, Models, ObjectModel, Sphere
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import CollisionObject, Generic, GenericWithPose, MultiArmRobot, Robot
from arcor2.object_types.utils import built_in_types_names, settings_from_params
from arcor2.parameter_plugins.base import TypesDict
from arcor2_execution_data import package


class ResourcesException(Arcor2Exception):
    pass


CUSTOM_OBJECT_TYPES_MODULE = "object_types"
R = TypeVar("R", bound="IntResources")

_shutting_down = Event()
_streaming_period = env.get_float("ARCOR2_STREAMING_PERIOD", 0.1)


def stream_pose(robot_inst: Robot) -> None:

    arm_eef: Dict[Optional[str], Set[str]] = {}

    try:
        if isinstance(robot_inst, MultiArmRobot):
            arms = robot_inst.get_arm_ids()
            arm_eef.update({arm: robot_inst.get_end_effectors_ids(arm) for arm in arms})
        else:
            arm_eef.update({None: robot_inst.get_end_effectors_ids()})

        while not _shutting_down.is_set():
            start = time.monotonic()
            print_event(
                RobotEef(
                    data=RobotEef.Data(
                        robot_inst.id,
                        [
                            RobotEef.Data.EefPose(eef, robot_inst.get_end_effector_pose(eef))
                            for arm, eefs in arm_eef.items()
                            for eef in eefs
                        ],
                    )
                )
            )
            time.sleep(_streaming_period - (time.monotonic() - start))
    except Arcor2Exception:
        # TODO save traceback to file?
        pass


def stream_joints(robot_inst: Robot) -> None:

    try:
        while not _shutting_down.is_set():
            start = time.monotonic()
            print_event(
                RobotJoints(data=RobotJoints.Data(robot_inst.id, robot_inst.robot_joints(include_gripper=True)))
            )
            time.sleep(_streaming_period - (time.monotonic() - start))
    except Arcor2Exception:
        # TODO save traceback to file?
        pass


class IntResources:

    __slots__ = ("project", "scene", "objects", "args", "executor", "_stream_futures")

    def __init__(self, scene: Scene, project: Project, models: Dict[str, Optional[Models]]) -> None:

        self.project = CachedProject(project)
        self.scene = CachedScene(scene)

        if self.project.scene_id != self.scene.id:
            raise ResourcesException("Project/scene not consistent!")

        type_defs: TypesDict = {}

        for scene_obj_type in self.scene.object_types:  # get all type-defs

            assert scene_obj_type not in type_defs
            assert scene_obj_type not in built_in_types_names()

            module = importlib.import_module(CUSTOM_OBJECT_TYPES_MODULE + "." + humps.depascalize(scene_obj_type))

            cls = getattr(module, scene_obj_type)
            patch_object_actions(cls)
            patch_with_action_mapping(cls, self.scene, self.project)
            type_defs[cls.__name__] = cls

        action.start_paused, action.breakpoints = parse_args()

        if action.breakpoints:
            ap_ids = self.project.action_points_ids
            for bp in action.breakpoints:
                if bp not in ap_ids:
                    raise ResourcesException(f"Breakpoint ID unknown: {bp}.")

        # orientations / joints have to be monkey-patched with AP's ID in order to make breakpoints work in @action
        for ap in self.project.action_points:

            setattr(ap.position, AP_ID_ATTR, ap.id)

            for joints in self.project.ap_joints(ap.id):
                setattr(joints, AP_ID_ATTR, ap.id)

        package_id = os.path.basename(os.getcwd())
        package_meta = package.read_package_meta(package_id)
        package_info_event = PackageInfo(PackageInfo.Data(package_id, package_meta.name, scene, project))

        for model in models.values():

            if not model:
                continue

            if isinstance(model, Box):
                package_info_event.data.collision_models.boxes.append(model)
            elif isinstance(model, Sphere):
                package_info_event.data.collision_models.spheres.append(model)
            elif isinstance(model, Cylinder):
                package_info_event.data.collision_models.cylinders.append(model)
            elif isinstance(model, Mesh):
                package_info_event.data.collision_models.meshes.append(model)

        # following steps might take some time, so let UIs know about the package as a first thing
        print_event(package_info_event)

        # in order to prepare a clean environment (clears all configurations and all collisions)
        scene_service.stop()

        self.executor = concurrent.futures.ThreadPoolExecutor()
        futures: List[concurrent.futures.Future] = []

        for scene_obj in self.scene.objects:

            cls = type_defs[scene_obj.type]
            settings = settings_from_params(cls, scene_obj.parameters, self.project.overrides.get(scene_obj.id, None))

            if issubclass(cls, Robot):
                futures.append(self.executor.submit(cls, scene_obj.id, scene_obj.name, scene_obj.pose, settings))
            elif issubclass(cls, CollisionObject):
                futures.append(
                    self.executor.submit(
                        cls, scene_obj.id, scene_obj.name, scene_obj.pose, models[scene_obj.type], settings
                    )
                )
            elif issubclass(cls, GenericWithPose):
                futures.append(self.executor.submit(cls, scene_obj.id, scene_obj.name, scene_obj.pose, settings))
            elif issubclass(cls, Generic):
                futures.append(self.executor.submit(cls, scene_obj.id, scene_obj.name, settings))
            else:
                raise Arcor2Exception("Unknown base class.")

        exception_cnt: int = 0

        self.objects: Dict[str, Generic] = {}

        for f in concurrent.futures.as_completed(futures):
            try:
                inst = f.result()  # if an object creation resulted in exception, it will be raised here
            except Arcor2Exception as e:
                print_exception(e)
                exception_cnt += 1  # count of objects that failed to initialize
            else:
                self.objects[inst.id] = inst  # successfully initialized objects

        if exception_cnt:  # if something failed, tear down those that succeeded and stop
            self.cleanup_all_objects()
            raise Arcor2Exception(f"Failed to initialize {exception_cnt} object(s).")

        scene_service.start()

        # make all poses absolute
        for aps in self.project.action_points_with_parent:
            # Action point pose is relative to its parent object/AP pose in scene but is absolute during runtime.
            tr.make_relative_ap_global(self.scene, self.project, aps)

        self._stream_futures: List[concurrent.futures.Future] = []

    def cleanup_all_objects(self) -> None:
        """Calls cleanup method of all objects in parallel.

        Errors are just logged.
        """

        futures: List[concurrent.futures.Future] = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for obj in self.objects.values():
                futures.append(executor.submit(obj.cleanup))
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Arcor2Exception as e:
                    print_exception(e)

    def __enter__(self: R) -> R:

        if _streaming_period > 0:  # TODO could be also controlled by script argument (RunPackage flag)
            for inst in self.objects.values():

                if not isinstance(inst, Robot):
                    continue

                self._stream_futures.append(self.executor.submit(stream_pose, inst))
                self._stream_futures.append(self.executor.submit(stream_joints, inst))

        return self

    def __exit__(
        self,
        ex_type: Optional[Type[BaseException]],
        ex_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:

        _shutting_down.set()

        try:
            concurrent.futures.wait(self._stream_futures, 1.0)
        except concurrent.futures.TimeoutError:
            pass

        if isinstance(ex_value, Exception):
            # this intentionally ignores KeyboardInterrupt (derived from BaseException)
            print_exception(ex_value)

        scene_service.stop()
        self.cleanup_all_objects()

        return True


T = TypeVar("T", bound=JsonSchemaMixin)


class Resources(IntResources):
    def read_project_data(self, file_name: str, cls: Type[T]) -> T:

        try:

            with open(os.path.join("data", file_name + ".json")) as scene_file:
                return cls.from_dict(humps.decamelize(json.loads(scene_file.read())))

        except JsonSchemaValidationError as e:
            raise ResourcesException(f"Invalid project/scene: {e}")

    def __init__(self) -> None:

        scene = self.read_project_data(Scene.__name__.lower(), Scene)
        project = self.read_project_data(Project.__name__.lower(), Project)

        models: Dict[str, Optional[Models]] = {}

        for obj in scene.objects:

            if obj.type in models:
                continue

            try:
                models[obj.type] = self.read_project_data("models/" + humps.depascalize(obj.type), ObjectModel).model()
            except IOError:
                models[obj.type] = None

        super().__init__(scene, project, models)
