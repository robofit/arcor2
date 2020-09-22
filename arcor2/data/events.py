# -*- coding: utf-8 -*-

import re
from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common, execution, object_type


def wo_suffix(name: str) -> str:
    return re.sub('Event$', '', name)


class EventType(common.StrEnum):

    ADD: str = "add"
    UPDATE: str = "update"
    REMOVE: str = "remove"
    UPDATE_BASE: str = "update_base"


"""
------------------------------------------------------------------------------------------------------------------------
Common stuff
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class Event(JsonSchemaMixin):

    event: str = field(default="", init=False)
    change_type: Optional[EventType] = None
    parent_id: Optional[str] = None


@dataclass
class ShowMainScreenData(JsonSchemaMixin):

    class WhatEnum(common.StrEnum):

        ScenesList: str = "ScenesList"
        ProjectsList: str = "ProjectsList"
        PackagesList: str = "PackagesList"

    what: WhatEnum
    highlight: Optional[str] = None


@dataclass
class ShowMainScreenEvent(Event):

    data: Optional[ShowMainScreenData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


"""
------------------------------------------------------------------------------------------------------------------------
Project / scene
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class OpenSceneData(JsonSchemaMixin):

    scene: common.Scene


@dataclass
class OpenScene(Event):

    data: Optional[OpenSceneData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneChanged(Event):

    data: Optional[common.Scene] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneSaved(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneClosed(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectChanged(Event):

    data: Optional[common.Project] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class OpenProjectData(JsonSchemaMixin):

    scene: common.Scene
    project: common.Project


@dataclass
class OpenProject(Event):

    data: Optional[OpenProjectData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectSaved(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectClosed(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionPointChanged(Event):

    data: Optional[common.ProjectActionPoint] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionChanged(Event):

    data: Optional[common.Action] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class LogicItemChanged(Event):

    data: Optional[common.LogicItem] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectConstantChanged(Event):

    data: Optional[common.ProjectConstant] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class OrientationChanged(Event):

    data: Optional[common.NamedOrientation] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class JointsChanged(Event):

    data: Optional[common.ProjectRobotJoints] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneObjectChanged(Event):

    data: Optional[common.SceneObject] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


"""
------------------------------------------------------------------------------------------------------------------------
Project execution
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ProjectExceptionEventData(JsonSchemaMixin):

    message: str = field(default_factory=str)
    type: str = field(default_factory=str)
    handled: bool = False


@dataclass
class ProjectExceptionEvent(Event):

    data: ProjectExceptionEventData = field(default_factory=ProjectExceptionEventData)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CurrentActionEvent(Event):

    data: common.CurrentAction = field(default_factory=common.CurrentAction)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PackageStateEvent(Event):

    data: common.PackageState = field(default_factory=common.PackageState)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PackageInfoEvent(Event):

    data: Optional[execution.PackageInfo] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class ActionStateEvent(Event):

    data: common.ActionState = field(default_factory=common.ActionState)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionExecutionData(JsonSchemaMixin):

    action_id: str = ""


@dataclass
class ActionExecutionEvent(Event):
    """
    Used to notify beginning of the action execution triggered while editing a project.
    """

    data: ActionExecutionData = field(default_factory=ActionExecutionData)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionResult(JsonSchemaMixin):

    action_id: str = ""
    result: Optional[str] = field(default=None, metadata=dict(description="JSON-encoded result of the action."))
    error: Optional[str] = None


@dataclass
class ActionResultEvent(Event):
    """
    Used to notify result of the action execution triggered while editing a project.
    """

    data: ActionResult = field(default_factory=ActionResult)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionCancelledEvent(Event):
    """
    Used to notify that the action execution was cancelled.
    """

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


"""
------------------------------------------------------------------------------------------------------------------------
Objects
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ChangedObjectTypesEvent(Event):

    data: List[object_type.ObjectTypeMeta] = field(default_factory=list)  # changed object types
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


"""
------------------------------------------------------------------------------------------------------------------------
Robots
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class RobotJointsData(JsonSchemaMixin):

    robot_id: str
    joints: List[common.Joint]


@dataclass
class RobotJointsEvent(Event):

    data: Optional[RobotJointsData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class EefPose(JsonSchemaMixin):

    end_effector_id: str
    pose: common.Pose


@dataclass
class RobotEefData(JsonSchemaMixin):

    robot_id: str
    end_effectors: List[EefPose] = field(default_factory=list)


@dataclass
class RobotEefEvent(Event):

    data: Optional[RobotEefData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821

# ----------------------------------------------------------------------------------------------------------------------


class MoveEventType(common.StrEnum):
    START: str = "start"
    END: str = "end"
    FAILED: str = "failed"


@dataclass
class RobotMoveToData(JsonSchemaMixin):

    move_event_type: MoveEventType
    robot_id: str


@dataclass
class RobotMoveToPoseData(RobotMoveToData):

    end_effector_id: str
    target_pose: common.Pose
    message: Optional[str] = None


@dataclass
class RobotMoveToPoseEvent(Event):

    data: Optional[RobotMoveToPoseData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToJointsData(RobotMoveToData):

    target_joints: List[common.Joint]
    message: Optional[str] = None


@dataclass
class RobotMoveToJointsEvent(Event):

    data: Optional[RobotMoveToJointsData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointOrientationData(RobotMoveToData):

    end_effector_id: str
    orientation_id: str
    message: Optional[str] = None


@dataclass
class RobotMoveToActionPointOrientationEvent(Event):

    data: Optional[RobotMoveToActionPointOrientationData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointJointsData(RobotMoveToData):

    joints_id: str
    message: Optional[str] = None


@dataclass
class RobotMoveToActionPointJointsEvent(Event):

    data: Optional[RobotMoveToActionPointJointsData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
