from dataclasses import dataclass
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin
from PIL.Image import Image

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Pose, StrEnum

from .abstract_with_pose import AbstractWithPose


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


class Search(AbstractWithPose):
    """REST interface to the search service (0.5.0)."""

    _ABSTRACT = False

    # --- Capture Controller -------------------------------------------------------------------------------------------

    def grab_image(self, *, an: Optional[str] = None) -> None:
        """Grabs image and stores to internal cache.

        :return:
        """
        rest.call(rest.Method.PUT, f"{self.settings.url}/capture/grab")

    def get_image(self, *, an: Optional[str] = None) -> Image:
        """Gets RGB image from internal cache, if there is any.

        :return:
        """

        return rest.get_image(f"{self.settings.url}/capture/image")

    def get_pose(self, *, an: Optional[str] = None) -> Pose:
        """Gets capture device pose in actual initialized spatial system space.

        :return:
        """
        return rest.call(rest.Method.GET, f"{self.settings.url}/capture/pose", return_type=Pose)

    def capture_export(self, path_to_save_zip: str, *, an: Optional[str] = None) -> None:
        """Gets the zipped captured data.

        :param path_to_save_zip: Where to save the zip file.
        :return:
        """

        rest.download(f"{self.settings.url}/capture/export", path_to_save_zip)

    # --- Pick Controller ----------------------------------------------------------------------------------------------

    def upsert_pick_args(
        self, item_id: str, suction_id: str, poses: List[PickArgs], *, an: Optional[str] = None
    ) -> None:
        """Adds or updates arguments required for pick given item with given
        suction.

        :param item_id:
        :param suction_id:
        :param poses:
        :return:
        """
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/pick/suctions",
            body=poses,
            params={"itemId": item_id, "suctionId": suction_id},
        )

    def compute_pick_args(
        self, item_id: str, suction_id: str, pose: Pose, *, an: Optional[str] = None
    ) -> List[PickArgs]:
        """Computes pick arguments for given suction, item and item pose.

        :param item_id:
        :param suction_id:
        :param pose:
        :return:
        """
        return rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/pick/suctions/compute",
            body=pose,
            params={"itemId": item_id, "suctionId": suction_id},
            list_return_type=PickArgs,
        )

    def upsert_gripper_args(
        self, item_id: str, gripper_id: str, gripper_setup: List[GripperSetup], *, an: Optional[str] = None
    ) -> None:
        """Adds or updates arguments required for pick given item with given
        gripper.

        :param item_id:
        :param gripper_id:
        :param gripper_setup:
        :return:
        """

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/pick/grippers",
            body=gripper_setup,
            params={"itemId": item_id, "gripperId": gripper_id},
        )

    def compute_gripper_args(
        self, item_id: str, gripper_id: str, pose: Pose, *, an: Optional[str] = None
    ) -> List[GripperSetup]:
        """Gets pick poses for specific tool and item.

        :param item_id:
        :param gripper_id:
        :param pose:
        :return:
        """

        return rest.call(
            rest.Method.GET,
            f"{self.settings.url}/pick/grippers/compute",
            list_return_type=GripperSetup,
            body=pose,
            params={"itemId": item_id, "gripperId": gripper_id},
        )

    # --- Search Controller --------------------------------------------------------------------------------------------

    def search(self, *, an: Optional[str] = None) -> SearchOutput:
        """Searches items based on search engine configuration and images
        stored in internal cache.

        :return:
        """
        return rest.call(rest.Method.GET, f"{self.settings.url}/search", return_type=SearchOutput)

    def set_search_parameters(self, parameters: SearchEngineParameters, *, an: Optional[str] = None) -> None:
        """Sets the search parameters.

        :param parameters:
        :return:
        """

        rest.call(rest.Method.PUT, f"{self.settings.url}/search", body=parameters)

    def visualization(self, *, an: Optional[str] = None) -> Image:
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
