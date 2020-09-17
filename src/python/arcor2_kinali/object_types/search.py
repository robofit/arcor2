from dataclasses import dataclass
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin
from PIL.Image import Image  # type: ignore

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Pose, StrEnum

from .kinali_abstract_object import KinaliAbstractObject


@dataclass
class ScoredItem(JsonSchemaMixin):

    id: int
    item_pose: Pose
    search_score: float


@dataclass
class SearchOutput(JsonSchemaMixin):

    items: List[ScoredItem]
    container_pose: Pose


@dataclass
class GripperSetup(JsonSchemaMixin):

    pick_speed: float
    pre_pick_opening: float
    pick_opening: float
    pick_force: float
    pick_pose: Pose


@dataclass
class SearchVisualizationSetup(JsonSchemaMixin):

    container: bool
    space_selector: bool
    estimate: bool
    refine: bool


@dataclass
class SearchSaveInfo(JsonSchemaMixin):

    save_input: bool
    save_visualizations: bool
    path: Optional[str] = None


class LogLevel(StrEnum):

    TRACE: str = "trace"
    DEBUG: str = "debug"
    INFO: str = "info"
    WARN: str = "warn"
    ERROR: str = "error"
    FATAL: str = "fatal"


@dataclass
class PickArgs(JsonSchemaMixin):

    pick_pose: Pose


@dataclass
class SearchLogLevel(JsonSchemaMixin):

    level: LogLevel


@dataclass
class SearchEngineParameters(JsonSchemaMixin):

    visualization_setup: Optional[SearchVisualizationSetup] = None
    search_data_save_info: Optional[SearchSaveInfo] = None
    search_log_level: Optional[SearchLogLevel] = None


class Search(KinaliAbstractObject):
    """REST interface to the search service (0.5.0)."""

    _ABSTRACT = False

    # --- Capture Controller -------------------------------------------------------------------------------------------

    def grab_image(self) -> None:
        """Grabs image and stores to internal cache.

        :return:
        """
        rest.put(f"{self.settings.url}/capture/grab")

    def get_image(self) -> Image:
        """Gets RGB image from internal cache, if there is any.

        :return:
        """

        return rest.get_image(f"{self.settings.url}/capture/image")

    def get_pose(self) -> Pose:
        """Gets capture device pose in actual initialized spatial system space.

        :return:
        """
        return rest.get(f"{self.settings.url}/capture/pose", Pose)

    # --- Pick Controller ----------------------------------------------------------------------------------------------

    def upsert_pick_args(self, item_id: str, suction_id: str, poses: List[PickArgs]) -> None:
        """Adds or updates arguments required for pick given item with given
        suction.

        :param item_id:
        :param suction_id:
        :param poses:
        :return:
        """
        rest.put(f"{self.settings.url}/pick/suctions", poses, {"itemId": item_id, "suctionId": suction_id})

    def compute_pick_args(self, item_id: str, suction_id: str, pose: Pose) -> List[PickArgs]:
        """Computes pick arguments for given suction, item and item pose.

        :param item_id:
        :param suction_id:
        :param pose:
        :return:
        """
        return rest.put_returning_list(
            f"{self.settings.url}/pick/suctions/compute", pose, {"itemId": item_id, "suctionId": suction_id}, PickArgs
        )

    def upsert_gripper_args(self, item_id: str, gripper_id: str, gripper_setup: List[GripperSetup]) -> None:
        """Adds or updates arguments required for pick given item with given
        gripper.

        :param item_id:
        :param gripper_id:
        :param gripper_setup:
        :return:
        """

        rest.put(f"{self.settings.url}/pick/grippers", gripper_setup, {"itemId": item_id, "gripperId": gripper_id})

    def compute_gripper_args(self, item_id: str, gripper_id: str, pose: Pose) -> List[GripperSetup]:
        """Gets pick poses for specific tool and item.

        :param item_id:
        :param gripper_id:
        :param pose:
        :return:
        """

        return rest.get_list(
            f"{self.settings.url}/pick/grippers/compute",
            GripperSetup,
            pose,
            {"itemId": item_id, "gripperId": gripper_id},
        )

    # --- Search Controller --------------------------------------------------------------------------------------------

    def search(self) -> SearchOutput:
        """Searches items based on search engine configuration and images
        stored in internal cache.

        :return:
        """
        return rest.get(f"{self.settings.url}/search", SearchOutput)

    def set_search_parameters(self, parameters: SearchEngineParameters) -> None:
        """Sets the search parameters.

        :param parameters:
        :return:
        """

        rest.put(f"{self.settings.url}/search", parameters)

    def visualization(self) -> Image:
        """Gets RGB visualization from last search run, if there is any.

        :return:
        """

        return rest.get_image(f"{self.settings.url}/search/visualization")

    grab_image.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_image.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_pose.__action__ = ActionMetadata(blocking=True)  # type: ignore

    upsert_pick_args.__action__ = ActionMetadata(blocking=True)  # type: ignore
    compute_pick_args.__action__ = ActionMetadata(blocking=True)  # type: ignore
    upsert_gripper_args.__action__ = ActionMetadata(blocking=True)  # type: ignore
    compute_gripper_args

    search.__action__ = ActionMetadata(blocking=True)  # type: ignore
    set_search_parameters.__action__ = ActionMetadata(blocking=True)  # type: ignore
    visualization.__action__ = ActionMetadata(blocking=True)  # type: ignore
