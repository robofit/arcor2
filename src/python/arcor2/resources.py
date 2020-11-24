import importlib
import json
import os
from typing import Any, Dict, Optional, Type, TypeVar

import humps
from dataclasses_jsonschema import JsonSchemaMixin, JsonSchemaValidationError

import arcor2.object_types
from arcor2 import package
from arcor2 import transformations as tr
from arcor2.action import patch_object_actions, print_event
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import scene_service
from arcor2.data.common import Project, Scene
from arcor2.data.events import CurrentAction, PackageInfo
from arcor2.data.object_type import Box, Cylinder, Mesh, Models, ObjectModel, Sphere
from arcor2.exceptions import Arcor2Exception
from arcor2.exceptions.runtime import print_exception
from arcor2.object_types.abstract import Generic, GenericWithPose, Robot
from arcor2.object_types.utils import built_in_types_names, settings_from_params
from arcor2.parameter_plugins.base import TypesDict
from arcor2.parameter_plugins.utils import plugin_from_type_name


class ResourcesException(Arcor2Exception):
    pass


R = TypeVar("R", bound="IntResources")


class IntResources:

    CUSTOM_OBJECT_TYPES_MODULE = "object_types"

    def __init__(self, scene: Scene, project: Project, models: Dict[str, Optional[Models]]) -> None:

        self.project = CachedProject(project)
        self.scene = CachedScene(scene)

        if self.project.scene_id != self.scene.id:
            raise ResourcesException("Project/scene not consistent!")

        self.objects: Dict[str, Generic] = {}

        self.type_defs: TypesDict = {}

        built_in = built_in_types_names()

        # workaround for possible 'An item with the same key has already been added.' problem
        scene_service.stop()

        scene_service.delete_all_collisions()

        package_id = os.path.basename(os.getcwd())
        package_meta = package.read_package_meta(package_id)
        package_info_event = PackageInfo(PackageInfo.Data(package_id, package_meta.name, scene, project))

        for scene_obj in self.scene.objects:

            if scene_obj.type in built_in:
                module = importlib.import_module(arcor2.object_types.__name__ + "." + humps.depascalize(scene_obj.type))
            else:
                module = importlib.import_module(
                    ResourcesBase.CUSTOM_OBJECT_TYPES_MODULE + "." + humps.depascalize(scene_obj.type)
                )

            cls = getattr(module, scene_obj.type)
            patch_object_actions(cls)
            self.type_defs[cls.__name__] = cls

            assert scene_obj.id not in self.objects, "Duplicate object id {}!".format(scene_obj.id)

            settings = settings_from_params(cls, scene_obj.parameters, self.project.overrides.get(scene_obj.id, None))

            if issubclass(cls, Robot):
                self.objects[scene_obj.id] = cls(scene_obj.id, scene_obj.name, scene_obj.pose, settings)
            elif issubclass(cls, GenericWithPose):
                self.objects[scene_obj.id] = cls(
                    scene_obj.id, scene_obj.name, scene_obj.pose, models[scene_obj.type], settings
                )
            elif issubclass(cls, Generic):
                self.objects[scene_obj.id] = cls(scene_obj.id, scene_obj.name, settings)
            else:
                raise Arcor2Exception("Unknown base class.")

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

    def make_all_poses_absolute(self) -> None:
        """This is only needed when the main script is written fully manually
        (actions are not defined in AR Editor).

        :return:
        """

        # make all poses absolute
        for aps in self.project.action_points_with_parent:
            # Action point pose is relative to its parent object/AP pose in scene but is absolute during runtime.
            tr.make_relative_ap_global(self.scene, self.project, aps)

    def __enter__(self: R) -> R:
        return self

    def __exit__(self, ex_type, ex_value, traceback) -> bool:

        if ex_type:  # TODO ignore when script is stopped correctly (e.g. KeyboardInterrupt, ??)
            print_exception(ex_type(ex_value))

        scene_service.stop()
        scene_service.delete_all_collisions()

        for obj in self.objects.values():
            obj.cleanup()

        return True

    def print_info(self, action_id: str, args: Dict[str, Any]) -> None:
        """Helper method used to print out info about the action going to be
        executed."""
        # TODO to be used for parameters that are result of previous action(s)
        # ...there is no need to send parameters that are already in the project
        print_event(CurrentAction(CurrentAction.Data(action_id)))

    def parameters(self, action_id: str) -> Dict[str, Any]:

        try:
            act = self.project.action(action_id)
        except Arcor2Exception:
            raise ResourcesException("Action_id {} not found in project {}.".format(action_id, self.project.id))

        ret: Dict[str, Any] = {}

        for param in act.parameters:
            ret[param.name] = plugin_from_type_name(param.type).parameter_execution_value(
                self.type_defs, self.scene, self.project, action_id, param.name
            )

        return ret


T = TypeVar("T", bound=JsonSchemaMixin)


def lower(s: str) -> str:

    return s.lower()


class ResourcesBase(IntResources):
    def read_project_data(self, file_name: str, cls: Type[T]) -> T:

        try:

            with open(os.path.join("data", file_name + ".json")) as scene_file:
                return cls.from_dict(humps.decamelize(json.loads(scene_file.read())))  # type: ignore

        except JsonSchemaValidationError as e:
            raise ResourcesException(f"Invalid project/scene: {e}")

    def __init__(self, project_id: str) -> None:

        scene = self.read_project_data(Scene.__name__.lower(), Scene)
        project = self.read_project_data(Project.__name__.lower(), Project)

        if project_id != project.id:
            raise ResourcesException("Resources were generated for different project!")

        models: Dict[str, Optional[Models]] = {}

        for obj in scene.objects:

            if obj.type in models:
                continue

            try:
                models[obj.type] = self.read_project_data("models/" + humps.depascalize(obj.type), ObjectModel).model()
            except IOError:
                models[obj.type] = None

        super(ResourcesBase, self).__init__(scene, project, models)
