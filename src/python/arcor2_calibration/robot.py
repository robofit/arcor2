import copy

import cv2
import numpy as np
import open3d as o3d
from PIL import Image
from urdfpy import URDF

from arcor2.data.camera import CameraParameters
from arcor2.data.common import Joint, Pose
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger

logger = get_logger(__name__)


class RobotCalibrationException(Arcor2Exception):
    pass


def depth_image_to_np(depth: Image.Image) -> np.ndarray:
    return np.array(depth, dtype=np.float32) / 1000.0


def draw_registration_result(obj, scene, initial_tr, icp_tr) -> None:

    initial_temp = copy.deepcopy(obj)
    aligned_temp = copy.deepcopy(obj)
    scene_temp = copy.deepcopy(scene)

    initial_temp.paint_uniform_color([1, 0, 0])
    aligned_temp.paint_uniform_color([0, 1, 0])
    scene_temp.paint_uniform_color([0, 0, 1])

    initial_temp.transform(initial_tr)
    aligned_temp.transform(icp_tr)

    mesh_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.1)

    o3d.visualization.draw_geometries([initial_temp, aligned_temp, scene_temp, mesh_frame])


def calibrate_robot(
    robot_joints: list[Joint],
    robot_pose: Pose,
    camera_pose: Pose,
    camera_parameters: CameraParameters,
    robot: URDF,
    depth_image: Image,
    draw_results: bool = False,
) -> Pose:

    logger.info("Creating robot model...")

    fk = robot.visual_trimesh_fk(cfg={joint.name: joint.value for joint in robot_joints})

    robot_tr_matrix = robot_pose.as_tr_matrix()

    res_mesh = o3d.geometry.TriangleMesh()

    for tm in fk:
        pose = fk[tm]
        mesh = o3d.geometry.TriangleMesh(
            vertices=o3d.utility.Vector3dVector(tm.vertices), triangles=o3d.utility.Vector3iVector(tm.faces)
        )
        mesh.transform(np.dot(robot_tr_matrix, pose))
        mesh.compute_vertex_normals()
        res_mesh += mesh

    mesh_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.1)

    sim_pcd = res_mesh.sample_points_uniformly(int(1e5))

    camera_tr_matrix = camera_pose.as_tr_matrix()
    camera_matrix = camera_parameters.as_camera_matrix()
    depth = depth_image_to_np(depth_image)

    wh = (depth_image.width, depth_image.height)

    dist = np.array(camera_parameters.dist_coefs)
    newcameramtx, _ = cv2.getOptimalNewCameraMatrix(camera_matrix, dist, wh, 1, wh)
    depth = cv2.undistort(depth, camera_matrix, dist, None, newcameramtx)

    real_pcd = o3d.geometry.PointCloud.create_from_depth_image(
        o3d.geometry.Image(depth),
        o3d.camera.PinholeCameraIntrinsic(
            depth_image.width,
            depth_image.height,
            camera_parameters.fx,
            camera_parameters.fy,
            camera_parameters.cx,
            camera_parameters.cy,
        ),
    )

    real_pcd.transform(camera_tr_matrix)

    bb = sim_pcd.get_axis_aligned_bounding_box()
    real_pcd = real_pcd.crop(bb.scale(1.25, bb.get_center()))

    # logger.info("Outlier removal...")
    # real_pcd = real_pcd.remove_radius_outlier(nb_points=50, radius=0.01)[0]

    sim_pcd = sim_pcd.select_by_index(sim_pcd.hidden_point_removal(np.array(list(camera_pose.position)), 500)[1])

    print("Estimating normals...")
    real_pcd.estimate_normals()

    if draw_results:
        o3d.visualization.draw_geometries([sim_pcd, real_pcd, mesh_frame])

    threshold = 1.0
    trans_init = np.identity(4)

    """
    evaluation = o3d.pipelines.registration.evaluate_registration(
        sim_pcd,
        real_pcd,
        threshold,
        trans_init,
    )

    logger.info(evaluation)
    """

    logger.info("Applying point-to-plane robust ICP...")

    loss = o3d.pipelines.registration.TukeyLoss(k=0.25)

    p2l = o3d.pipelines.registration.TransformationEstimationPointToPlane(loss)
    reg_p2p = o3d.pipelines.registration.registration_icp(
        sim_pcd,
        real_pcd,
        threshold,
        trans_init,
        p2l,
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=100),
    )

    logger.info(reg_p2p)
    logger.debug(reg_p2p.transformation)

    # TODO somehow check if calibration is ok

    if draw_results:
        draw_registration_result(sim_pcd, real_pcd, trans_init, reg_p2p.transformation)

    robot_tr_matrix = np.dot(reg_p2p.transformation, robot_tr_matrix)
    pose = Pose.from_tr_matrix(robot_tr_matrix)

    logger.info("Done")

    return pose
