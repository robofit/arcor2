from arcor2 import helpers as hlp
from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import (
    Action,
    ActionParameter,
    LogicItem,
    Parameter,
    ProjectFunction,
    ProjectParameter,
    SceneObject,
)
from arcor2.exceptions import Arcor2Exception
from arcor2.logic import LogicContainer
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.utils import known_parameter_types, plugin_from_type_name
from arcor2_arserver.object_types.data import ObjectTypeData, ObjectTypeDict
from arcor2_arserver.objects_actions import get_types_dict
from arcor2_arserver_data.objects import ObjectAction

# TODO refactor the module somewhere, so it can be also used within arcor2_build?


def find_object_action(obj_types: ObjectTypeDict, scene: CachedScene, action: Action) -> ObjectAction:

    obj_id, action_type = action.parse_type()
    obj = scene.object(obj_id)
    obj_type = obj_types[obj.type]

    try:
        act = obj_type.actions[action_type]
    except KeyError:
        raise Arcor2Exception("Unknown type of action.")

    if act.disabled:
        raise Arcor2Exception("Action is disabled.")

    return act


# TODO refactor into arcor2.logic?
def check_logic_item(
    obj_types: ObjectTypeDict, scene: CachedScene, parent: LogicContainer, logic_item: LogicItem
) -> None:
    """Checks if newly added/updated ProjectLogicItem is ok.

    :param parent:
    :param logic_item:
    :return:
    """

    action_ids = parent.action_ids()

    if logic_item.start == LogicItem.START and logic_item.end == LogicItem.END:
        raise Arcor2Exception("This does not make sense.")

    if logic_item.start != LogicItem.START:

        start_action_id, start_flow = logic_item.parse_start()

        if start_action_id == logic_item.end:
            raise Arcor2Exception("Start and end can't be the same.")

        if start_action_id not in action_ids:
            raise Arcor2Exception("Logic item has unknown start.")

        if start_flow != "default":  # TODO enum
            raise Arcor2Exception("Only flow 'default' is supported so far.'")

    if logic_item.end != LogicItem.END:

        if logic_item.end not in action_ids:
            raise Arcor2Exception("Logic item has unknown end.")

    if logic_item.condition is not None:

        what = logic_item.condition.parse_what()
        action = parent.action(what.action_id)  # action that produced the result which we depend on here
        flow = action.flow(what.flow_name)
        try:
            flow.outputs[what.output_index]
        except IndexError:
            raise Arcor2Exception(f"Flow {flow.type} does not have output with index {what.output_index}.")

        action_meta = find_object_action(obj_types, scene, action)

        try:
            return_type = action_meta.returns[what.output_index]
        except IndexError:
            raise Arcor2Exception(f"Invalid output index {what.output_index} for action {action_meta.name}.")

        return_type_plugin = plugin_from_type_name(return_type)

        if not return_type_plugin.COUNTABLE:
            raise Arcor2Exception(f"Output of type {return_type} can't be branched.")

        # TODO for now there is only support for bool
        if return_type_plugin.type() != bool:
            raise Arcor2Exception("Unsupported condition type.")

        # check that condition value is ok, actual value is not interesting
        # TODO perform this check using plugin
        from arcor2 import json

        if not isinstance(json.loads(logic_item.condition.value), bool):
            raise Arcor2Exception("Invalid condition value.")

    for existing_item in parent.logic:

        if existing_item.id == logic_item.id:  # item is updated
            continue

        if logic_item.start == logic_item.START and existing_item.start == logic_item.START:
            raise Arcor2Exception("START already defined.")

        if logic_item.start == existing_item.start:

            if None in (logic_item.condition, existing_item.condition):
                raise Arcor2Exception("Two junctions has the same start action without condition.")

            # when there are more logical connections from A to B, their condition values must be different
            if logic_item.condition == existing_item.condition:
                raise Arcor2Exception("Two junctions with the same start should have different conditions.")

        if logic_item.end == existing_item.end:
            if logic_item.start == existing_item.start:
                raise Arcor2Exception("Junctions can't have the same start and end.")


def check_parameter(parameter: Parameter) -> None:

    # TODO check using (some) plugin
    from arcor2 import json

    val = json.loads(parameter.value)

    # however, analysis in get_dataclass_params() can handle also (nested) dataclasses, etc.
    if not isinstance(val, (int, float, str, bool)):
        raise Arcor2Exception("Only basic types are supported so far.")


def check_object_parameters(obj_type: ObjectTypeData, parameters: list[Parameter]) -> None:

    if {s.name for s in obj_type.meta.settings if s.default_value is None} > {s.name for s in parameters}:
        raise Arcor2Exception("Some required parameter is missing.")

    param_dict = obj_type.meta.parameters_dict()

    for param in parameters:

        if param_dict[param.name].type != param.type:
            raise Arcor2Exception(f"Type mismatch for parameter {param}.")

        check_parameter(param)


def check_project_parameter(proj: CachedProject, parameter: ProjectParameter) -> None:

    hlp.is_valid_identifier(parameter.name)

    for pparam in proj.parameters:

        if parameter.id == pparam.id:
            continue

        if parameter.name == pparam.name:
            raise Arcor2Exception(f"Project parameter name {parameter.name} is duplicate.")

    check_parameter(parameter)


def check_object(obj_types: ObjectTypeDict, scene: CachedScene, obj: SceneObject, new_one: bool = False) -> None:
    """Checks if object can be added into the scene."""

    if obj.type not in obj_types:
        raise Arcor2Exception(f"Unknown ObjectType {obj.type}.")

    obj_type = obj_types[obj.type]

    if obj_type.meta.disabled:
        raise Arcor2Exception(f"ObjectType {obj.type} is disabled. {obj_type.meta.problem}")

    check_object_parameters(obj_type, obj.parameters)

    # TODO check whether object needs parent and if so, if the parent is in scene and parent_id is set
    if obj_type.meta.needs_parent_type:
        pass

    if obj_type.meta.has_pose and obj.pose is None:
        raise Arcor2Exception(f"Object {obj.name} requires pose.")

    if not obj_type.meta.has_pose and obj.pose is not None:
        raise Arcor2Exception(f"Object {obj.name} should not have pose.")

    if obj_type.meta.abstract:
        raise Arcor2Exception(f"ObjectType {obj.type} is abstract.")

    if new_one:

        if obj.id in scene.object_ids:
            raise Arcor2Exception(f"Object {obj.name} has duplicate id.")

        if obj.name in scene.object_names():
            raise Arcor2Exception(f"Object name {obj.name} is duplicate.")

    hlp.is_valid_identifier(obj.name)


def check_action_params(
    obj_types: ObjectTypeDict, scene: CachedScene, project: CachedProject, action: Action, object_action: ObjectAction
) -> None:

    _, action_type = action.parse_type()

    assert action_type == object_action.name

    if len(object_action.parameters) != len(action.parameters):
        raise Arcor2Exception("Unexpected number of parameters.")

    for req_param in object_action.parameters:

        param = action.parameter(req_param.name)

        if param.type == ActionParameter.TypeEnum.PROJECT_PARAMETER:

            pparam = project.parameter(param.str_from_value())

            param_meta = object_action.parameter(param.name)
            if param_meta.type != pparam.type:
                raise Arcor2Exception("Action parameter type does not match project parameter type.")

        elif param.type == ActionParameter.TypeEnum.LINK:

            parsed_link = param.parse_link()

            if parsed_link.action_id == action.id:
                raise Arcor2Exception("Can't use own result as a parameter.")

            parent_action = project.action(parsed_link.action_id)
            source_action_pt = parent_action.parse_type()

            parent_action_meta = obj_types[scene.object(source_action_pt.obj_id).type].actions[
                source_action_pt.action_type
            ]

            if len(parent_action.flow(parsed_link.flow_name).outputs) != len(parent_action_meta.returns):
                raise Arcor2Exception("Source action does not have outputs specified.")

            param_meta = object_action.parameter(param.name)

            try:
                if param_meta.type != parent_action_meta.returns[parsed_link.output_index]:
                    raise Arcor2Exception("Param type does not match action output type.")
            except IndexError:
                raise Arcor2Exception(
                    f"Index {parsed_link.output_index} is invalid for action {object_action.name},"
                    f" which returns {len(object_action.returns)} values."
                )

        else:

            if param.type not in known_parameter_types():
                raise Arcor2Exception(f"Parameter {param.name} of action {action.name} has unknown type: {param.type}.")

            try:
                plugin_from_type_name(param.type).parameter_value(
                    get_types_dict(), scene, project, action.id, param.name
                )
            except ParameterPluginException as e:
                raise Arcor2Exception(f"Parameter {param.name} of action {action.name} has invalid value. {str(e)}")


def check_flows(parent: CachedProject | ProjectFunction, action: Action, action_meta: ObjectAction) -> None:
    """Raises exception if there is something wrong with flow(s).

    :param parent:
    :param action:
    :param action_meta:
    :return:
    """

    flow = action.flow()  # searches default flow (just this flow is supported so far)

    # it is ok to not specify any output (if the values are not going to be used anywhere)
    # return value(s) won't be stored in variable(s)
    if not flow.outputs:
        return

    # otherwise, all return values have to be stored in variables
    if len(flow.outputs) != len(action_meta.returns):
        raise Arcor2Exception("Number of the flow outputs does not match the number of action outputs.")

    for output in flow.outputs:
        hlp.is_valid_identifier(output)

    outputs: set[str] = set()

    for act in parent.actions:
        for fl in act.flows:
            for output in fl.outputs:
                if output in outputs:
                    raise Arcor2Exception(f"Output '{output}' is not unique.")


def scene_problems(obj_types: ObjectTypeDict, scene: CachedScene) -> list[str]:

    problems: list[str] = []

    for scene_obj in scene.objects:
        try:
            check_object(obj_types, scene, scene_obj)
        except Arcor2Exception as e:
            problems.append(str(e))

    return problems


def check_ap_parent(scene: CachedScene, proj: CachedProject, parent: None | str) -> None:

    if not parent:
        return

    if parent in scene.object_ids:
        if scene.object(parent).pose is None:
            raise Arcor2Exception("AP can't have object without pose as parent.")
    elif parent not in proj.action_points_ids:
        raise Arcor2Exception("AP has invalid parent ID (not an object or another AP).")


def project_problems(obj_types: ObjectTypeDict, scene: CachedScene, project: CachedProject) -> list[str]:

    if project.scene_id != scene.id:
        return ["Project/scene mismatch."]

    problems: list[str] = scene_problems(obj_types, scene)

    for proj_param in project.parameters:
        try:
            check_project_parameter(project, proj_param)
        except Arcor2Exception as e:
            problems.append(str(e))

    for ap in project.action_points:

        try:
            check_ap_parent(scene, project, ap.parent)
        except Arcor2Exception:
            problems.append(f"Action point {ap.name} has invalid parent: {ap.parent}.")

        for joints in project.ap_joints(ap.id):
            if joints.robot_id not in scene.object_ids:
                problems.append(
                    f"Action point {ap.name} has joints ({joints.name}) for an unknown robot: {joints.robot_id}."
                )

        for action in project.actions:

            # check if objects have used actions
            obj_id, action_type = action.parse_type()

            if obj_id not in scene.object_ids:
                problems.append(f"Object ID {obj_id} which action is used in {action.name} does not exist in scene.")
                continue

            scene_obj = scene.object(obj_id)
            if action_type not in obj_types[scene_obj.type].actions:
                problems.append(
                    f"ObjectType {scene_obj.type} does not have action {action_type} used in {action.name}."
                )
                continue

            action_meta = obj_types[scene_obj.type].actions[action_type]

            try:
                check_action_params(obj_types, scene, project, action, action_meta)
            except Arcor2Exception as e:
                problems.append(str(e))

            try:
                check_flows(project, action, action_meta)
            except Arcor2Exception as e:
                problems.append(str(e))

    return problems
