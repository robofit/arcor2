#!/usr/bin/env python3

import argparse
import ast
import logging
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import TypeVar

import humps
from dataclasses_jsonschema import JsonSchemaMixin, ValidationError
from flask import request, send_file

import arcor2_build
from arcor2 import env, json
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import project_service as ps
from arcor2.data.common import Project, ProjectSources, Scene
from arcor2.data.execution import PackageMeta
from arcor2.data.object_type import Models, ObjectModel, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url, save_and_import_type_def
from arcor2.logging import get_logger
from arcor2.object_types.abstract import Generic
from arcor2.object_types.utils import base_from_source, built_in_types_names, prepare_object_types_dir
from arcor2.parameter_plugins.base import TypesDict
from arcor2.source import SourceException
from arcor2.source.utils import parse
from arcor2_build.source.logic import program_src
from arcor2_build.source.utils import global_action_points_class
from arcor2_build_data import DEPENDENCIES, SERVICE_NAME, URL, ImportResult
from arcor2_build_data.exceptions import Conflict, InvalidPackage, InvalidProject, NotFound, WebApiError

OBJECT_TYPE_MODULE = "arcor2_object_types"

original_sys_path = list(sys.path)
original_sys_modules = dict(sys.modules)

logger = get_logger("Build")

app = create_app(__name__)


def get_base_from_project_service(
    types_dict: TypesDict,
    tmp_dir: str,
    scene_object_types: set[str],
    obj_type: ObjectType,
    zf: zipfile.ZipFile,
    ot_path: str,
    ast: ast.AST,
) -> None:

    for idx, base in enumerate(base_from_source(ast, obj_type.id)):

        if base in types_dict.keys() | built_in_types_names() | scene_object_types:
            continue

        logger.debug(f"Getting {base} as base of {obj_type.id}.")
        base_obj_type = ps.get_object_type(base)

        # first try if the code is valid
        try:
            base_ast = parse(base_obj_type.source)
        except Arcor2Exception:
            raise InvalidPackage(f"Invalid code of the {base_obj_type.id} (base of {obj_type.id}).")

        # try to get base of the base
        get_base_from_project_service(types_dict, tmp_dir, scene_object_types, base_obj_type, zf, ot_path, base_ast)

        if idx == 0:  # this is the base ObjectType
            types_dict[base_obj_type.id] = save_and_import_type_def(
                base_obj_type.source, base_obj_type.id, Generic, tmp_dir, OBJECT_TYPE_MODULE
            )
        else:  # these are potential mixins (just try to import them, no need to store them)
            save_and_import_type_def(base_obj_type.source, base_obj_type.id, object, tmp_dir, OBJECT_TYPE_MODULE)
            scene_object_types.add(base_obj_type.id)

        zf.writestr(os.path.join(ot_path, humps.depascalize(base_obj_type.id)) + ".py", base_obj_type.source)


def get_base_from_imported_package(
    obj_type: ObjectType, types_dict: dict[str, ObjectType], zip_file: zipfile.ZipFile, tmp_dir: str, ast: ast.AST
) -> None:

    for idx, base in enumerate(base_from_source(ast, obj_type.id)):

        if base in types_dict.keys() | built_in_types_names():
            continue

        logger.debug(f"Getting {base} as base of {obj_type.id}.")

        try:
            base_obj_type_src = read_str_from_zip(zip_file, f"object_types/{humps.depascalize(base)}.py")
        except KeyError:
            raise InvalidPackage(f"Could not find {base} object type (base of {obj_type.id}).")

        # first try if the code is valid
        try:
            base_ast = parse(base_obj_type_src)
        except Arcor2Exception:
            raise InvalidPackage(f"Invalid code of the {base} (base of {obj_type.id}).")

        types_dict[base] = ObjectType(base, base_obj_type_src)

        # try to get base of the base
        get_base_from_imported_package(types_dict[base], types_dict, zip_file, tmp_dir, base_ast)

        # then, try to import it (no need to store the result)
        if idx == 0:  # this is the base ObjectType
            save_and_import_type_def(base_obj_type_src, base, Generic, tmp_dir, OBJECT_TYPE_MODULE)
        else:  # these are potential mixins
            save_and_import_type_def(base_obj_type_src, base, object, tmp_dir, OBJECT_TYPE_MODULE)


def _publish(project_id: str, package_name: str) -> RespT:

    mem_zip = BytesIO()

    logger.debug(f"Generating package {package_name} for project_id: {project_id}.")

    types_dict: TypesDict = {}

    # restore original environment
    sys.path = list(original_sys_path)
    sys.modules = dict(original_sys_modules)

    with tempfile.TemporaryDirectory() as tmp_dir:

        prepare_object_types_dir(tmp_dir, OBJECT_TYPE_MODULE)

        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

            try:
                logger.debug("Getting scene and project.")
                project = ps.get_project(project_id)
                cached_project = CachedProject(project)
                scene = ps.get_scene(project.scene_id)
                cached_scene = CachedScene(scene)

                if not package_name:
                    package_name = project.name

                data_path = "data"
                ot_path = "object_types"

                zf.writestr(os.path.join(ot_path, "__init__.py"), "")
                zf.writestr(os.path.join(data_path, "project.json"), project.to_json())
                zf.writestr(os.path.join(data_path, "scene.json"), scene.to_json())

                obj_types = set(cached_scene.object_types)
                obj_types_with_models: set[str] = set()

                if __debug__:  # this should uncover potential problems with order in which ObjectTypes are processed
                    import random

                    random.shuffle(scene.objects)

                for scene_obj in scene.objects:

                    if scene_obj.type in types_dict:
                        continue

                    logger.debug(f"Getting scene object type {scene_obj.type}.")
                    obj_type = ps.get_object_type(scene_obj.type)

                    if obj_type.model and obj_type.id not in obj_types_with_models:
                        obj_types_with_models.add(obj_type.id)

                        model = ps.get_model(obj_type.model.id, obj_type.model.type)
                        obj_model = ObjectModel(
                            obj_type.model.type, **{model.type().value.lower(): model}  # type: ignore
                        )

                        zf.writestr(
                            os.path.join(data_path, "models", humps.depascalize(obj_type.id) + ".json"),
                            obj_model.to_json(),
                        )

                    zf.writestr(os.path.join(ot_path, humps.depascalize(obj_type.id)) + ".py", obj_type.source)

                    # handle inheritance
                    get_base_from_project_service(
                        types_dict, tmp_dir, obj_types, obj_type, zf, ot_path, parse(obj_type.source)
                    )

                    types_dict[scene_obj.type] = save_and_import_type_def(
                        obj_type.source, scene_obj.type, Generic, tmp_dir, OBJECT_TYPE_MODULE
                    )

            except Arcor2Exception as e:
                logger.exception(f"Failed to prepare package content. {str(e)}")
                raise NotFound(str(e))

            script_path = "script.py"

            try:

                if project.has_logic:
                    logger.debug("Generating script from project logic.")
                    zf.writestr(script_path, program_src(types_dict, cached_project, cached_scene, True))
                else:
                    try:
                        logger.debug("Getting project sources.")
                        script = ps.get_project_sources(project.id).script

                        # check if it is a valid Python code
                        try:
                            parse(script)
                        except SourceException:
                            logger.exception("Failed to parse code of the uploaded script.")
                            raise InvalidProject("Invalid source code.")

                        zf.writestr(script_path, script)

                    except ps.ProjectServiceException:

                        logger.info("Script not found on project service, creating one from scratch.")

                        # write script without the main loop
                        zf.writestr(script_path, program_src(types_dict, cached_project, cached_scene, False))

                logger.debug("Generating supplementary files.")

                logger.debug("action_points.py")
                zf.writestr("action_points.py", global_action_points_class(cached_project))

                logger.debug("package.json")
                zf.writestr("package.json", PackageMeta(package_name, datetime.now(tz=timezone.utc)).to_json())

            except Arcor2Exception as e:
                logger.exception("Failed to generate script.")
                raise InvalidProject(str(e))

    logger.info(f"Done with {package_name} (scene {scene.name}, project {project.name}).")
    mem_zip.seek(0)

    return send_file(mem_zip, as_attachment=True, max_age=0, download_name=f"{package_name}_package.zip")


@app.route("/project/publish", methods=["GET"])
def project_publish() -> RespT:
    """Publish project
    ---
    get:
      tags:
        - Project
      summary: Gets the Execution package.
      operationId: ProjectPublish
      parameters:
        - in: query
          name: projectId
          schema:
            type: string
          required: true
          description: Id of the project to be published.
        - in: query
          name: packageName
          schema:
            type: string
          required: false
          description: Name to be used for package created.
      responses:
        200:
          description: Returns archive of the execution package (.zip).
          content:
            application/zip:
                schema:
                  type: string
                  format: binary
        500:
          description: "Error types: **General**, **NotFound**, **InvalidProject**."
          content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    return _publish(request.args["projectId"], request.args.get("packageName", default=""))


T = TypeVar("T", bound=JsonSchemaMixin)


def read_str_from_zip(zip_file: zipfile.ZipFile, file_name: str) -> str:

    return zip_file.read(file_name).decode("UTF-8")


def read_dc_from_zip(zip_file: zipfile.ZipFile, file_name: str, cls: type[T]) -> T:

    return cls.from_dict(humps.decamelize(json.loads_type(read_str_from_zip(zip_file, file_name), dict)))


@app.route("/project/import", methods=["PUT"])
def project_import() -> RespT:
    """Imports a project from execution package.
    ---
    put:
      tags:
        - Project
      summary: Imports a project from execution package.
      operationId: ProjectImport
      parameters:
            - in: query
              name: overwriteScene
              schema:
                type: boolean
                default: false
              description: Replace existing scene.json with new one for specified project.
            - in: query
              name: overwriteProject
              schema:
                type: boolean
                default: false
              description: Replace existing project.json with new one for specified project.
            - in: query
              name: overwriteObjectTypes
              schema:
                type: boolean
                default: false
              description: Replace existing Object Type definition with new one for specified project.
            - in: query
              name: overwriteProjectSources
              schema:
                type: boolean
                default: false
              description: Replace all existing project sources with new ones.
            - in: query
              name: overwriteCollisionModels
              schema:
                type: boolean
                default: false
              description: Replace existing collision models with new ones for specified project.
      requestBody:
              content:
                multipart/form-data:
                  schema:
                    type: object
                    required:
                        - executionPackage
                    properties:
                      executionPackage:
                        type: string
                        format: binary
      responses:
        200:
          description: Project was successfully imported.
          content:
                application/json:
                  schema:
                    $ref: ImportResult
        500:
          description: "Error types: **General**, **NotFound**, **InvalidPackage**, **Conflict**."
          content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    file = request.files["executionPackage"]

    overwrite_scene = request.args.get("overwriteScene", default="false") == "true"
    overwrite_project = request.args.get("overwriteProject", default="false") == "true"
    overwrite_object_types = request.args.get("overwriteObjectTypes", default="false") == "true"
    overwrite_project_sources = request.args.get("overwriteProjectSources", default="false") == "true"
    overwrite_collision_models = request.args.get("overwriteCollisionModels", default="false") == "true"

    objects: dict[str, ObjectType] = {}
    models: dict[str, Models] = {}

    """
    1) get and validate all data from zip
    2) check what is already on the Project service
    3) do updates
    """
    # BytesIO + stream.read() = workaround for a Python bug (SpooledTemporaryFile not seekable)
    with zipfile.ZipFile(BytesIO(file.stream.read())) as zip_file:

        try:
            project = read_dc_from_zip(zip_file, "data/project.json", Project)
        except KeyError:
            raise NotFound("Could not find project.json.")
        except (json.JsonException, ValidationError) as e:
            raise InvalidPackage(f"Failed to process project.json. {str(e)}")

        try:
            scene = read_dc_from_zip(zip_file, "data/scene.json", Scene)
        except KeyError:
            raise NotFound("Could not find scene.json.")
        except (json.JsonException, ValidationError) as e:
            raise InvalidPackage(f"Failed to process scene.json. {str(e)}")

        if project.scene_id != scene.id:
            raise InvalidPackage("Project assigned to different scene id.")

        with tempfile.TemporaryDirectory() as tmp_dir:

            # restore original environment
            sys.path = list(original_sys_path)
            sys.modules = dict(original_sys_modules)

            prepare_object_types_dir(tmp_dir, OBJECT_TYPE_MODULE)

            for scene_obj in scene.objects:

                obj_type_name = scene_obj.type

                if obj_type_name in objects:  # there might be more instances of the same type
                    continue

                logger.debug(f"Importing {obj_type_name}.")

                try:
                    obj_type_src = read_str_from_zip(zip_file, f"object_types/{humps.depascalize(obj_type_name)}.py")
                except KeyError:
                    raise NotFound(f"Object type {obj_type_name} is missing in the package.")

                try:
                    ast = parse(obj_type_src)
                except Arcor2Exception:
                    raise InvalidPackage(f"Invalid code of the {obj_type_name} object type.")

                # TODO fill in OT description (is it used somewhere?)
                objects[obj_type_name] = ObjectType(obj_type_name, obj_type_src)
                get_base_from_imported_package(objects[obj_type_name], objects, zip_file, tmp_dir, ast)

                type_def = save_and_import_type_def(obj_type_src, obj_type_name, Generic, tmp_dir, OBJECT_TYPE_MODULE)

                assert obj_type_name == type_def.__name__

                if type_def.abstract():
                    raise InvalidPackage(f"Scene contains abstract object type: {obj_type_name}.")

        for obj_type in objects.values():  # handle models

            # TODO rather iterate on content of data/models?
            try:
                model = read_dc_from_zip(
                    zip_file, f"data/models/{humps.depascalize(obj_type.id)}.json", ObjectModel
                ).model()
            except KeyError:
                continue

            logger.debug(f"Found model {model.id} of type {model.type}.")

            obj_type.model = model.metamodel()

            if obj_type.id != obj_type.model.id:
                raise InvalidPackage(
                    f"Model id ({obj_type.model.id}) has to be the same as ObjectType id ({obj_type.id}).",
                )

            models[obj_type.id] = model

        if not project.has_logic:
            logger.debug("Importing the main script.")

            try:
                script = zip_file.read("script.py").decode("UTF-8")
            except KeyError:
                raise NotFound("Could not find script.py.")

            try:
                parse(script)
            except Arcor2Exception:
                raise InvalidPackage("Invalid code of the main script.")

    # check that we are not going to overwrite something
    if not overwrite_scene:

        try:
            ps_scene = ps.get_scene(scene.id)
        except ps.ProjectServiceException:
            pass
        else:

            # do not take created / modified into account
            ps_scene.created = scene.created = None
            ps_scene.modified = scene.modified = None

            if ps_scene != scene:
                raise Conflict("Scene difference detected. Overwrite needed.")

    if not overwrite_project:

        try:
            ps_project = ps.get_project(project.id)
        except ps.ProjectServiceException:
            pass
        else:

            # do not take created / modified into account
            ps_project.created = project.created = None
            ps_project.modified = project.modified = None

            if ps_project != project:
                raise Conflict("Project difference detected. Overwrite needed.")

    if not overwrite_object_types:

        for obj_type in objects.values():

            try:

                ot = ps.get_object_type(obj_type.id)

                # ignore changes in description (no one cares)
                if ot.source != obj_type.source or ot.model != obj_type.model:
                    raise Conflict(f"Difference detected for {obj_type.id} object type. Overwrite needed.")
            except ps.ProjectServiceException:
                pass

    if not overwrite_project_sources and not project.has_logic:

        try:
            if ps.get_project_sources(project.id).script != script:
                raise Conflict("Script difference detected. Overwrite needed.")
        except ps.ProjectServiceException:
            pass

    if not overwrite_collision_models:

        for model in models.values():
            try:
                if model != ps.get_model(model.id, model.type()):
                    raise Conflict("Collision model difference detected. Overwrite needed.")
            except ps.ProjectServiceException:
                pass

    for model in models.values():
        ps.put_model(model)

    for obj_type in objects.values():
        ps.update_object_type(obj_type)

    ps.update_scene(scene)
    ps.update_project(project)
    if not project.has_logic:
        ps.update_project_sources(ProjectSources(project.id, script))

    logger.info(
        f"Imported project {project.name} (scene {scene.name}), with {len(objects)} "
        f"object type(s) and {len(models)} model(s)."
    )

    return ImportResult(scene.id, project.id).to_json(), 200


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_BUILD_DEBUG") else logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)

    run_app(
        app,
        SERVICE_NAME,
        arcor2_build.version(),
        port_from_url(URL),
        [ImportResult, WebApiError],
        print_spec=args.swagger,
        dependencies=DEPENDENCIES,
    )


if __name__ == "__main__":
    main()
