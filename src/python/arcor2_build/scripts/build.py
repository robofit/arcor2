#!/usr/bin/env python3

import argparse
import json
import logging
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from json.decoder import JSONDecodeError
from typing import Dict, Set, Type, TypeVar

import humps
from dataclasses_jsonschema import JsonSchemaMixin, ValidationError
from flask import request, send_file

import arcor2_build
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import persistent_storage as ps
from arcor2.data.common import Project, ProjectSources, Scene
from arcor2.data.execution import PackageMeta
from arcor2.data.object_type import Models, ObjectModel, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.flask import FlaskException, RespT, create_app, run_app
from arcor2.helpers import port_from_url, save_and_import_type_def
from arcor2.logging import get_logger
from arcor2.object_types.abstract import Generic
from arcor2.object_types.utils import base_from_source, built_in_types_names, prepare_object_types_dir
from arcor2.parameter_plugins.base import TypesDict
from arcor2.source import SourceException
from arcor2.source.utils import parse
from arcor2_build.source.logic import program_src
from arcor2_build.source.utils import global_action_points_class
from arcor2_build_data import SERVICE_NAME, URL

OBJECT_TYPE_MODULE = "arcor2_object_types"

original_sys_path = list(sys.path)
original_sys_modules = dict(sys.modules)

logger = get_logger("Build")

app = create_app(__name__)


def get_base(
    types_dict: TypesDict,
    tmp_dir: str,
    scene_object_types: Set[str],
    obj_type: ObjectType,
    zf: zipfile.ZipFile,
    ot_path: str,
) -> None:

    base = base_from_source(obj_type.source, obj_type.id)

    if base is None:
        raise Arcor2Exception(f"Could not determine base class for {obj_type.id}.")

    if base in types_dict.keys() | built_in_types_names() | scene_object_types:
        return

    logger.debug(f"Getting {base} as base of {obj_type.id}.")
    base_obj_type = ps.get_object_type(base)

    zf.writestr(os.path.join(ot_path, humps.depascalize(base_obj_type.id)) + ".py", base_obj_type.source)

    types_dict[base_obj_type.id] = save_and_import_type_def(
        base_obj_type.source, base_obj_type.id, Generic, tmp_dir, OBJECT_TYPE_MODULE
    )

    # try to get base of the base
    get_base(types_dict, tmp_dir, scene_object_types, base_obj_type, zf, ot_path)


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

                data_path = "data"
                ot_path = "object_types"

                zf.writestr(os.path.join(ot_path, "__init__.py"), "")
                zf.writestr(os.path.join(data_path, "project.json"), project.to_json())
                zf.writestr(os.path.join(data_path, "scene.json"), scene.to_json())

                obj_types = set(cached_scene.object_types)
                obj_types_with_models: Set[str] = set()

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
                    get_base(types_dict, tmp_dir, obj_types, obj_type, zf, ot_path)

                    types_dict[scene_obj.type] = save_and_import_type_def(
                        obj_type.source, scene_obj.type, Generic, tmp_dir, OBJECT_TYPE_MODULE
                    )

            except Arcor2Exception as e:
                logger.exception("Failed to get something from the project service.")
                raise FlaskException(str(e), error_code=404)

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
                            raise FlaskException("Invalid code.", error_code=501)

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
                raise FlaskException(str(e), error_code=501)

    logger.debug("Execution package finished.")
    mem_zip.seek(0)
    return send_file(mem_zip, as_attachment=True, cache_timeout=0, attachment_filename="arcor2_project.zip")


@app.route("/project/<string:project_id>/publish", methods=["GET"])
def project_publish(project_id: str) -> RespT:
    """Publish project
    ---
    get:
      description: Get zip file with execution package. To be used by the Execution service.
      parameters:
        - in: path
          name: project_id
          schema:
            type: string
          required: true
          description: unique ID
        - in: query
          name: packageName
          schema:
            type: string
            default: N/A
          required: false
          description: Package name
      responses:
        200:
          description: Ok
          content:
            application/zip:
                schema:
                  type: string
                  format: binary
                  example: The archive of execution package (.zip)
        404:
            description: Project ID or some of the required items was not found.
        501:
            description: Project invalid.
    """

    return _publish(project_id, request.args.get("packageName", default="N/A"))


T = TypeVar("T", bound=JsonSchemaMixin)


def read_str_from_zip(zip_file: zipfile.ZipFile, file_name: str) -> str:

    return zip_file.read(file_name).decode("UTF-8")


def read_dc_from_zip(zip_file: zipfile.ZipFile, file_name: str, cls: Type[T]) -> T:

    return cls.from_dict(humps.decamelize(json.loads(read_str_from_zip(zip_file, file_name))))


@app.route("/project/import", methods=["PUT"])
def project_import() -> RespT:
    """Imports a project from execution package.
    ---
    put:
      description: Imports a project from execution package.
      parameters:
            - in: query
              name: overwrite
              schema:
                type: boolean
                default: false
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
          description: Ok
          content:
                application/json:
                  schema:
                    type: string
        400:
          description: Some other error occurred.
          content:
                application/json:
                  schema:
                    type: string
        401:
          description: Invalid execution package.
          content:
                application/json:
                  schema:
                    type: string
        402:
          description: A difference between package/project service detected (overwrite needed).
          content:
                application/json:
                  schema:
                    type: string
        404:
          description: Something is missing.
          content:
                application/json:
                  schema:
                    type: string
    """

    file = request.files["executionPackage"]
    overwrite = request.args.get("overwrite", default="false") == "true"

    objects: Dict[str, ObjectType] = {}
    models: Dict[str, Models] = {}

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
            raise FlaskException("Could not find project.json.", error_code=404)
        except (JSONDecodeError, ValidationError) as e:
            raise FlaskException(f"Failed to process project.json. {str(e)}", error_code=401)

        try:
            scene = read_dc_from_zip(zip_file, "data/scene.json", Scene)
        except KeyError:
            raise FlaskException("Could not find scene.json.", error_code=404)
        except (JSONDecodeError, ValidationError) as e:
            return json.dumps(f"Failed to process scene.json. {str(e)}"), 401

        if project.scene_id != scene.id:
            raise FlaskException("Project assigned to different scene id.", error_code=401)

        for scene_obj in scene.objects:

            obj_type_name = scene_obj.type

            if obj_type_name in objects:
                continue

            try:
                obj_type_src = read_str_from_zip(zip_file, f"object_types/{humps.depascalize(obj_type_name)}.py")
            except KeyError:
                raise FlaskException(f"Object type {obj_type_name} is missing in the package.", error_code=404)

            try:
                parse(obj_type_src)
            except Arcor2Exception:
                raise FlaskException(f"Invalid code of the {obj_type_name} object type.", error_code=401)

            # TODO description (is it used somewhere?)
            objects[obj_type_name] = ObjectType(obj_type_name, obj_type_src)

            logger.debug(f"Just imported {obj_type_name}.")

            while True:
                base = base_from_source(obj_type_src, obj_type_name)

                if not base:
                    return json.dumps(f"Could not determine base class for {scene_obj.type}."), 401

                if base in objects.keys() | built_in_types_names():
                    break

                logger.debug(f"Importing {base} as a base of {obj_type_name}.")

                try:
                    base_obj_type_src = read_str_from_zip(zip_file, f"object_types/{humps.depascalize(base)}.py")
                except KeyError:
                    return json.dumps(f"Could not find {base} object type (base of {obj_type_name})."), 404

                try:
                    parse(base_obj_type_src)
                except Arcor2Exception:
                    return json.dumps(f"Invalid code of the {base} object type (base of {obj_type_name})."), 401

                objects[base] = ObjectType(base, base_obj_type_src)

                obj_type_name = base
                obj_type_src = base_obj_type_src

        for obj_type in objects.values():  # handle models

            try:
                model = read_dc_from_zip(
                    zip_file, f"data/models/{humps.depascalize(obj_type.id)}.json", ObjectModel
                ).model()
            except KeyError:
                continue

            logger.debug(f"Found model {model.id} of type {model.type}.")

            obj_type.model = model.metamodel()

            if obj_type.id != obj_type.model.id:
                raise FlaskException(
                    f"Model id ({obj_type.model.id}) has to be the same as ObjectType id ({obj_type.id}).",
                    error_code=401,
                )

            models[obj_type.id] = model

        if not project.has_logic:
            logger.debug("Importing the main script.")

            try:
                script = zip_file.read("script.py").decode("UTF-8")
            except KeyError:
                raise FlaskException("Could not find script.py.", error_code=404)

            try:
                parse(script)
            except Arcor2Exception:
                raise FlaskException("Invalid code of the main script.", error_code=401)

    if not overwrite:  # check that we are not going to overwrite something

        try:
            if ps.get_scene(scene.id) != scene:
                raise FlaskException("Scene difference detected. Overwrite needed.", error_code=402)
        except ps.ProjectServiceException:
            pass

        try:
            if ps.get_project(project.id) != project:
                raise FlaskException("Project difference detected. Overwrite needed.", error_code=402)
        except ps.ProjectServiceException:
            pass

        for obj_type in objects.values():

            try:
                if ps.get_object_type(obj_type.id) != obj_type:
                    raise FlaskException("Scene difference detected. Overwrite needed.", error_code=402)
            except ps.ProjectServiceException:
                pass

        if not project.has_logic:

            try:
                if ps.get_project_sources(project.id).script != script:
                    raise FlaskException("Script difference detected. Overwrite needed.", error_code=402)
            except ps.ProjectServiceException:
                pass

        # TODO check also models?

    for model in models.values():
        ps.put_model(model)

    for obj_type in objects.values():
        ps.update_object_type(obj_type)

    ps.update_scene(scene)
    ps.update_project(project)
    if not project.has_logic:
        ps.update_project_sources(ProjectSources(project.id, script))

    return (
        json.dumps(
            f"Imported project {project.name} (scene {scene.name}), with {len(objects)} "
            f"object type(s) and {len(models)} model(s)."
        ),
        200,
    )


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)

    run_app(
        app, SERVICE_NAME, arcor2_build.version(), arcor2_build.version(), port_from_url(URL), print_spec=args.swagger
    )


if __name__ == "__main__":
    main()
