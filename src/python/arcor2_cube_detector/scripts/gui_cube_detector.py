import io
import os
import zipfile
from enum import Enum

import numpy as np
import open3d as o3d
from open3d.visualization import gui, rendering

from arcor2 import rest
from arcor2.data.camera import CameraParameters
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger
from arcor2_cube_detector import get_data
from arcor2_cube_detector.cube_detector import Color, CubeDetector, Plane

logger = get_logger(__name__)


class ComboColors(Enum):
    ALL = 0
    RED = 1
    GREEN = 2
    BLUE = 3
    YELLOW = 4


URL_KINECT = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://localhost:5016")
HALF_OF_CUBE_SIZE = 0.0125

paint_color: list[list[int]] = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]]


class GUI:
    def Menu(self, name: str, sections: list) -> gui.CollapsableVert:
        menu = gui.CollapsableVert(name, 4, gui.Margins(16, 0, 0, 0))
        for section in sections:
            menu.add_child(section)
            menu.add_fixed(8)
        return menu

    def Horizontal(self, childs) -> gui.Horiz:
        h = gui.Horiz(0.25 * 16)
        h.add_stretch()
        for child in childs:
            h.add_child(child)
        h.add_stretch()
        return h

    def Button(self, name, callback) -> gui.Button:
        button = gui.Button(name)
        button.horizontal_padding_em = 0.5
        button.vertical_padding_em = 0
        button.set_on_clicked(callback)
        return button

    def Number(self, startValue, callback) -> gui.NumberEdit:
        number = gui.NumberEdit(gui.NumberEdit.Type.INT)
        number.set_limits(0, 80)
        number.int_value = startValue
        number.set_on_value_changed(callback)
        return number

    def ComboBox(self, items, callback) -> gui.Combobox:
        comboBox = gui.Combobox()
        for item in items:
            comboBox.add_item(item.name)
        comboBox.set_on_selection_changed(callback)
        return comboBox

    def Label(self, name):
        return gui.Label(name)


class Visualizer:
    def __init__(self) -> None:
        self.init_GUI()
        self.init_detector()

    def init_GUI(self) -> None:
        """Initialize GUI components."""
        self.GUI_App = gui.Application.instance
        self.GUI_App.initialize()

        self.gui_window = gui.Application.instance.create_window("Cube detector", 1024, 768)
        self.gui_scene = gui.SceneWidget()
        self.gui_scene.scene = rendering.Open3DScene(self.gui_window.renderer)
        self.gui_scene.set_view_controls(gui.SceneWidget.Controls.PICK_POINTS)

        self.main_menu = gui.Vert(0, gui.Margins(4, 4, 4, 4))

        self.selected_colors = list(Color)
        self.labelCluster = gui.Label("Cluster 0/0")

        gui_control = GUI()

        menus = [
            gui_control.Menu(
                "Data source",
                [
                    gui_control.Horizontal(
                        [
                            gui_control.Button("Kinect API", self.set_source_kinect),
                            gui_control.Button("Dataset", self.set_source_dataset),
                        ]
                    ),
                ],
            ),
            gui_control.Menu(
                "Dataset folder",
                [
                    gui_control.Horizontal([gui_control.Number(0, self.change_folder)]),
                ],
            ),
            gui_control.Menu(
                "View",
                [
                    gui_control.Horizontal(
                        [gui_control.Label("COLOR"), gui_control.ComboBox(ComboColors, self.change_detected_color)]
                    ),
                    gui_control.Horizontal(
                        [
                            gui_control.Button("Original", self.show_original),
                            gui_control.Button("Filter", self.show_filtered),
                            gui_control.Button("Clusters", self.show_clusters),
                        ]
                    ),
                    gui_control.Horizontal(
                        [
                            gui_control.Button("Single cluster", self.show_individual_clusters),
                            gui_control.Number(0, self.change_cluster),
                        ]
                    ),
                ],
            ),
            gui_control.Menu(
                "Detection",
                [
                    gui_control.Horizontal(
                        [
                            gui_control.Button("Segment planes", self.show_segmented_planes),
                            gui_control.Button("Detect cubes", self.show_detected_cubes),
                        ]
                    ),
                ],
            ),
        ]

        for menu in menus:
            self.main_menu.add_child(menu)
            self.main_menu.add_fixed(8)

        self.gui_window.set_on_layout(self._on_layout)
        self.gui_window.add_child(self.gui_scene)
        self.gui_window.add_child(self.main_menu)

    def run(self) -> None:
        gui.Application.instance.run()

    def _on_layout(self, layout_context: gui.LayoutContext) -> None:
        self.gui_scene.frame = self.gui_window.content_rect
        width = 17 * layout_context.theme.font_size
        height = min(
            self.gui_window.content_rect.height,
            self.main_menu.calc_preferred_size(layout_context, gui.Widget.Constraints()).height,
        )
        self.main_menu.frame = gui.Rect(
            self.gui_window.content_rect.get_right() - width, self.gui_window.content_rect.y, width, height
        )

    def init_detector(self) -> None:
        """Initialize detector variables and load starting pointcloud."""
        self.folder = 0
        self.labels: list[gui.Label3D] = []
        self.set_source_dataset()

    def remove_labels(self) -> None:
        for label in self.labels:
            self.gui_scene.remove_3d_label(label)

    def set_source_kinect(self) -> None:
        """Loads image from Kinect API."""
        try:
            kinect_started = rest.call(rest.Method.GET, f"{URL_KINECT}/state/started", return_type=bool)
        except Arcor2Exception:
            logger.warning("Kinect is not started")
            return
        if not kinect_started:
            logger.warning("Kinect is not started")
            return

        self.detector = CubeDetector(
            rest.call(rest.Method.GET, f"{URL_KINECT}/color/parameters", return_type=CameraParameters)
        )

        synchronized = rest.call(rest.Method.GET, f"{URL_KINECT}/synchronized/image", return_type=io.BytesIO)
        with zipfile.ZipFile(synchronized, mode="r") as zip:
            color = zip.read("color.jpg")
            depth = zip.read("depth.png")
        self.color, self.depth = self.detector.get_image_from_bytes(color, depth)
        self.create_pointcloud()

    def set_source_dataset(self) -> None:
        """Set dataset as data source, initialize detector and parameters."""
        self.camera_parameters = CameraParameters(
            907.80126953125,
            907.6754150390625,
            960.291259765625,
            552.93536376953125,
            [0.447, -2.5, 0.00094, -0.00053, 1.432, 0.329, -2.332, 1.363],
        )
        self.detector = CubeDetector(self.camera_parameters)
        self.load_folder()

    def change_detected_color(self, name: str, index: int) -> None:
        """Change detected color.

        :param name: value of combobox option
        :param index: index of combobox option
        """
        self.selected_colors = list(Color) if index == 0 else [list(Color)[index - 1]]
        self.load_folder()

    def change_folder(self, folder: int) -> None:
        """Change folder containing data.

        :param folder: number of folder
        """
        if folder >= 0:
            self.folder = int(folder)
            self.load_folder()
        else:
            logger.warning(f"Folder {int(folder)} doesn't exist")

    def load_folder(self) -> None:
        path = get_data(f"dataset/{self.folder}")

        if not os.path.exists(f"{path}/color.jpg"):
            logger.warning(f"Folder {self.folder} doesn't exist")
            return
        self.color, self.depth = self.detector.get_image_from_file(f"{path}/color.jpg", f"{path}/depth.png")
        self.create_pointcloud()

    def create_pointcloud(self) -> None:
        """Create pointcloud from loaded source."""
        self.remove_labels()
        rgbd_image = o3d.geometry.RGBDImage.create_from_color_and_depth(
            self.color, self.depth, convert_rgb_to_intensity=False
        )
        self.pcd_original = (
            o3d.geometry.PointCloud()
            .create_from_rgbd_image(
                rgbd_image,
                o3d.camera.PinholeCameraIntrinsic(
                    1920,
                    1080,
                    self.camera_parameters.fx,
                    self.camera_parameters.fy,
                    self.camera_parameters.cx,
                    self.camera_parameters.cy,
                ),
            )
            .transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
            .voxel_down_sample(voxel_size=0.0015)
        )

        self.pcd_filtered: dict[Color, o3d.geometry.PointCloud] = {}
        self.pcd_clusters: dict[Color, list[o3d.geometry.PointCloud]] = {}
        self.cluster_count = 0
        self.selected_cluster_index = 0

        self.show_original()

        self.gui_scene.setup_camera(
            60, self.gui_scene.scene.bounding_box, self.gui_scene.scene.bounding_box.get_center()
        )

    def show_original(self) -> None:
        """Show original pointcloud."""
        self.remove_labels()
        self.gui_scene.scene.clear_geometry()
        self.gui_scene.scene.add_geometry(
            "pcd_original", self.pcd_original, o3d.visualization.rendering.MaterialRecord()
        )

    def show_filtered(self) -> None:
        """Show filtered pointcloud."""
        self.remove_labels()
        self.gui_scene.scene.clear_geometry()
        self.pcd_filtered = self.detector.filter_pointcloud(self.color, self.depth)
        for color in self.selected_colors:
            self.pcd_filtered[color].transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
            self.gui_scene.scene.add_geometry(
                f"__pcdFiltered{color}__", self.pcd_filtered[color], o3d.visualization.rendering.MaterialRecord()
            )

    def show_clusters(self) -> None:
        """Show pointclouds for each cluster."""
        self.remove_labels()
        if not self.pcd_filtered:
            self.show_filtered()
        self.gui_scene.scene.clear_geometry()
        self.cluster_count = 0

        for color in self.selected_colors:
            self.pcd_clusters[color] = self.detector.dbscan(self.pcd_filtered[color])
            self.cluster_count += len(self.pcd_clusters[color])
            for j in range(len(self.pcd_clusters[color])):
                self.gui_scene.scene.add_geometry(
                    f"__pcdCluster{color}{j}__",
                    self.pcd_clusters[color][j],
                    o3d.visualization.rendering.MaterialRecord(),
                )
        self.labelCluster.text = f"Cluster 0/{self.cluster_count}"

    def show_individual_clusters(self) -> None:
        """Set index of selected cluster to 0 and display it."""
        self.remove_labels()
        self.selected_cluster_index = 0
        self.show_individual_cluster()

    def show_individual_cluster(self) -> None:
        """Show pointcloud of selected cluster."""
        self.remove_labels()
        if not self.pcd_clusters:
            self.show_clusters()
        self.gui_scene.scene.clear_geometry()
        self.labelCluster.text = f"Cluster {self.selected_cluster_index + 1}/{self.cluster_count}"
        index = 0
        for color in self.selected_colors:
            for i in range(len(self.pcd_clusters[color])):
                if index == self.selected_cluster_index:
                    self.gui_scene.scene.add_geometry(
                        f"__pcdCluster{self.selected_cluster_index}__",
                        self.pcd_clusters[color][i],
                        o3d.visualization.rendering.MaterialRecord(),
                    )
                    self.selected_cluster = self.pcd_clusters[color][i]
                    return
                index += 1

    def change_cluster(self, cluster: int) -> None:
        """Change index of selected cluster.

        :param cluster: index of cluster
        """
        self.remove_labels()
        if cluster >= 0 and cluster < self.cluster_count:
            self.selected_cluster_index = int(cluster)
        else:
            logger.warning(f"Cluster {int(cluster)} doesn't exist ({0}-{self.cluster_count-1})")

        self.show_individual_cluster()

    def show_segmented_planes(self) -> None:
        """Show segmented planes."""
        self.remove_labels()
        if not self.pcd_clusters:
            self.show_clusters()
        self.gui_scene.scene.clear_geometry()

        for color in self.selected_colors:
            for j in range(len(self.pcd_clusters[color])):
                planes = self.detector.segment_plane(self.pcd_clusters[color][j])
                for k in range(len(planes)):
                    planes[k].pointcloud.paint_uniform_color(paint_color[k % len(paint_color)])
                    self.gui_scene.scene.add_geometry(
                        f"__pcdCluster{color}{j}Plane{k}__",
                        planes[k].pointcloud,
                        o3d.visualization.rendering.MaterialRecord(),
                    )

    def show_detected_cubes(self) -> None:
        """Show detected cubes."""
        self.remove_labels()
        if not self.pcd_clusters:
            self.show_clusters()
        self.gui_scene.scene.clear_geometry()

        number_of_detected_cubes = 0

        for color in self.selected_colors:
            for j in range(len(self.pcd_clusters[color])):
                planes = self.detector.segment_plane(self.pcd_clusters[color][j])
                angle_of_planes = self.detector.get_angles_between_planes(planes)
                for candidate in self.detector.find_candidates(angle_of_planes):
                    if self.detector.detect_cube([planes[i] for i in candidate], False):
                        self.show_detected_cube([planes[i] for i in candidate], f"{color}{j}")
                        number_of_detected_cubes += 1
                        break

        logger.info(f"Detected {number_of_detected_cubes} cubes")

    def show_detected_cube(self, planes: list[Plane], name: str) -> None:
        """Simplified version of method detect_cube() from cube_detector.py."""
        cube_pointcloud = o3d.geometry.PointCloud()
        for plane_pointcloud, _ in planes:
            cube_pointcloud += plane_pointcloud

        points = np.asarray(cube_pointcloud.points)

        number_of_sides = len(planes)

        edge_points: list = number_of_sides * [None]
        for i in range(number_of_sides):
            edge_points[i] = [
                point
                for point in points
                if self.detector.is_point_on_edge(point, [planes[i].model, planes[(i + 1) % number_of_sides].model])
            ]
        edge = o3d.geometry.PointCloud()
        edge.points = o3d.utility.Vector3dVector(sum(edge_points, []))
        edge.paint_uniform_color([0, 0, 0])

        if number_of_sides == 3:
            corner = o3d.geometry.PointCloud()
            corner.points = o3d.utility.Vector3dVector(
                [
                    point
                    for point in points
                    if self.detector.is_point_on_corner(point, [plane.model for plane in planes])
                ]
            )
            corner.paint_uniform_color([1, 0, 0])
            center = np.asarray(corner.get_center())

            self.gui_scene.scene.add_geometry(
                f"__pcdCube{name}Corner",
                corner,
                o3d.visualization.rendering.MaterialRecord(),
            )
        else:
            center = np.asarray(edge.get_center())

        vector: list[list[np.float64]] = []
        for i in range(number_of_sides):
            if number_of_sides == 3:
                edge_center = o3d.geometry.PointCloud()
                edge_center.points = o3d.utility.Vector3dVector(edge_points[i])
                edge_center = edge_center.get_center()
            else:
                edge_center = planes[i].pointcloud.get_center()

            label = self.gui_scene.add_3d_label(edge_center, "X")
            label.color = gui.Color(paint_color[1][0], paint_color[1][1], paint_color[1][2])
            self.labels.append(label)

            vector.append([])
            for j in range(3):
                vector[i].append(edge_center[j] - center[j])

            norm = np.linalg.norm(vector[i])
            if norm != 0:
                vector[i] = [vector / norm for vector in vector[i]]

        for i in range(3):
            for j in range(number_of_sides):
                center[i] += vector[j][i] * HALF_OF_CUBE_SIZE

        label = self.gui_scene.add_3d_label(center, "C")
        label.color = gui.Color(paint_color[0][0], paint_color[0][1], paint_color[0][2])
        self.labels.append(label)

        self.gui_scene.scene.add_geometry(
            f"__pcdCube{name}__",
            cube_pointcloud,
            o3d.visualization.rendering.MaterialRecord(),
        )
        self.gui_scene.scene.add_geometry(
            f"__pcdCube{name}Edge__",
            edge,
            o3d.visualization.rendering.MaterialRecord(),
        )


def main() -> None:
    visualizer = Visualizer()
    visualizer.run()


if __name__ == "__main__":
    main()
