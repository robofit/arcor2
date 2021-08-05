import concurrent.futures
import importlib
import os
from types import TracebackType
from typing import Dict, List, Optional, Type, TypeVar

import humps
from dataclasses_jsonschema import JsonSchemaMixin, JsonSchemaValidationError

from arcor2 import json
from arcor2 import transformations as tr
from arcor2.action import get_action_name_to_id, patch_object_actions, print_event
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import scene_service
from arcor2.data.common import Project, Scene
from arcor2.data.events import PackageInfo
from arcor2.data.object_type import Box, Cylinder, Mesh, Models, ObjectModel, Sphere
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import CollisionObject, Generic, GenericWithPose, Robot
from arcor2.object_types.utils import built_in_types_names, settings_from_params
from arcor2.parameter_plugins.base import TypesDict
from arcor2_execution_data import package
from arcor2_execution_data.exceptions import print_exception


class ResourcesException(Arcor2Exception):
    pass


CUSTOM_OBJECT_TYPES_MODULE = "object_types"
R = TypeVar("R", bound="IntResources")


class IntResources:

    __slots__ = ("project", "scene", "objects")

    def __init__(self, scene: Scene, project: Project, models: Dict[str, Optional[Models]]) -> None:

        self.project = CachedProject(project)
        self.scene = CachedScene(scene)

        if self.project.scene_id != self.scene.id:
            raise ResourcesException("Project/scene not consistent!")

        self.objects: Dict[str, Generic] = {}

        type_defs: TypesDict = {}

        # in order to prepare a clean environment (clears all configurations and all collisions)
        scene_service.stop()

        package_id = os.path.basename(os.getcwd())
        package_meta = package.read_package_meta(package_id)
        package_info_event = PackageInfo(PackageInfo.Data(package_id, package_meta.name, scene, project))

        for scene_obj_type in self.scene.object_types:  # get all type-defs

            assert scene_obj_type not in type_defs
            assert scene_obj_type not in built_in_types_names()

            module = importlib.import_module(CUSTOM_OBJECT_TYPES_MODULE + "." + humps.depascalize(scene_obj_type))

            cls = getattr(module, scene_obj_type)
            patch_object_actions(cls, get_action_name_to_id(self.scene, self.project, cls.__name__))
            type_defs[cls.__name__] = cls

        futures: List[concurrent.futures.Future] = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for scene_obj in self.scene.objects:

                cls = type_defs[scene_obj.type]

                assert scene_obj.id not in self.objects, "Duplicate object id {}!".format(scene_obj.id)

                settings = settings_from_params(
                    cls, scene_obj.parameters, self.project.overrides.get(scene_obj.id, None)
                )

                if issubclass(cls, Robot):
                    futures.append(executor.submit(cls, scene_obj.id, scene_obj.name, scene_obj.pose, settings))
                elif issubclass(cls, CollisionObject):
                    futures.append(
                        executor.submit(
                            cls, scene_obj.id, scene_obj.name, scene_obj.pose, models[scene_obj.type], settings
                        )
                    )
                elif issubclass(cls, GenericWithPose):
                    futures.append(executor.submit(cls, scene_obj.id, scene_obj.name, scene_obj.pose, settings))
                elif issubclass(cls, Generic):
                    futures.append(executor.submit(cls, scene_obj.id, scene_obj.name, settings))
                else:
                    raise Arcor2Exception("Unknown base class.")

            exception_cnt: int = 0

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

        scene_service.start()

        print_event(package_info_event)

        # make all poses absolute
        for aps in self.project.action_points_with_parent:
            # Action point pose is relative to its parent object/AP pose in scene but is absolute during runtime.
            tr.make_relative_ap_global(self.scene, self.project, aps)

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
        return self

    def __exit__(
        self,
        ex_type: Optional[Type[BaseException]],
        ex_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:

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
