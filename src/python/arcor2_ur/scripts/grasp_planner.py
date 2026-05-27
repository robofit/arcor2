import math

import numpy as np
import open3d as o3d
from shape_msgs.msg import Mesh as RosMesh  # pants: no-infer-dep

from arcor2.data import object_type
from arcor2.data.common import Orientation, Pose, Position
from arcor2_ur.common import CollisionSceneObject, EffectorType, GraspPosition

PRE_GRASP_OFFSET = 0.12
GRASP_OFFSET = 0.06


def generate_grasp_poses(
    obj: CollisionSceneObject,
    effector_type: EffectorType,
    grasp_position: GraspPosition = GraspPosition.ALL,
    ros_mesh: RosMesh | None = None,
) -> list[tuple[Pose, Pose]]:

    mesh = object_to_mesh(obj, ros_mesh)

    geometry = filter_geometry_by_grasp_position(mesh, grasp_position)

    candidates = create_grasp_candidates_from_surfaces(geometry, effector_type)

    candidates.sort(key=candidate_sort_key)

    return candidates[:20]


def object_to_mesh(obj: CollisionSceneObject, ros_mesh: RosMesh | None) -> o3d.geometry.TriangleMesh:
    """Box/Cylinder/Sphere/Mesh -> Open3D world mesh."""

    model = obj.model

    if isinstance(model, object_type.Box):
        mesh = o3d.geometry.TriangleMesh.create_box(width=model.size_x, height=model.size_y, depth=model.size_z)
        mesh.translate((-model.size_x / 2, -model.size_y / 2, -model.size_z / 2))

    elif isinstance(model, object_type.Cylinder):
        mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=model.radius, height=model.height)

    elif isinstance(model, object_type.Sphere):
        mesh = o3d.geometry.TriangleMesh.create_sphere(radius=model.radius)

    elif isinstance(model, object_type.Mesh):
        if ros_mesh is None:
            raise ValueError("Object is Mesh, but ros_mesh is None.")
        mesh = o3d.geometry.TriangleMesh()
        mesh.vertices = o3d.utility.Vector3dVector([(vertex.x, vertex.y, vertex.z) for vertex in ros_mesh.vertices])
        mesh.triangles = o3d.utility.Vector3iVector([tuple(triangle.vertex_indices) for triangle in ros_mesh.triangles])

    else:
        raise ValueError(f"Unsupported object model: {type(model).__name__}")

    apply_pose_to_mesh(mesh, obj.pose)
    mesh.compute_triangle_normals()
    mesh.compute_vertex_normals()
    return mesh


def apply_pose_to_mesh(mesh: o3d.geometry.TriangleMesh, pose: Pose) -> None:
    q = pose.orientation
    rotation = quaternion_to_rotation_matrix(q)

    mesh.rotate(rotation, center=(0.0, 0.0, 0.0))
    mesh.translate((pose.position.x, pose.position.y, pose.position.z))


def quaternion_to_rotation_matrix(q: Orientation) -> np.ndarray:
    x, y, z, w = q.x, q.y, q.z, q.w

    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0.0:
        raise ValueError("Invalid quaternion.")

    x, y, z, w = x / norm, y / norm, z / norm, w / norm

    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def filter_geometry_by_grasp_position(
    mesh: o3d.geometry.TriangleMesh,
    grasp_position: GraspPosition = GraspPosition.ALL,
) -> o3d.geometry.TriangleMesh:
    """TOP/BOTTOM/LEFT/RIGHT/FRONT/BACK filter."""

    if grasp_position == GraspPosition.ALL:
        return mesh

    mesh.compute_triangle_normals()

    triangles = np.asarray(mesh.triangles)
    normals = np.asarray(mesh.triangle_normals)

    wanted_dirs = {
        GraspPosition.BOTTOM: (0.0, 0.0, -1.0),
        GraspPosition.BACK: (0.0, 1.0, 0.0),
        GraspPosition.FRONT: (0.0, -1.0, 0.0),
        GraspPosition.LEFT: (-1.0, 0.0, 0.0),
        GraspPosition.RIGHT: (1.0, 0.0, 0.0),
        GraspPosition.TOP: (0.0, 0.0, 1.0),
    }

    kept = []
    for triangle, normal in zip(triangles, normals):
        direction = wanted_dirs[grasp_position]
        if dot(normal, direction) >= 0.707:  # maximum allowed rotation from the original normal: 45°
            kept.append(triangle)

    filtered = o3d.geometry.TriangleMesh()
    filtered.vertices = mesh.vertices
    filtered.triangles = o3d.utility.Vector3iVector(kept)
    filtered.compute_triangle_normals()
    filtered.compute_vertex_normals()

    return filtered


def dot(a, b) -> float:
    return float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])


def create_grasp_candidates_from_surfaces(
    mesh: o3d.geometry.TriangleMesh, effector_type: EffectorType
) -> list[tuple[Pose, Pose]]:
    """Mesh triangles -> list[(pre_grasp_pose, grasp_pose)]."""

    mesh.compute_triangle_normals()

    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    normals = np.asarray(mesh.triangle_normals)

    poses = []

    for triangle, normal in zip(triangles, normals):
        normal = normalize_vector((float(normal[0]), float(normal[1]), float(normal[2])))
        center = vertices[triangle].mean(axis=0)
        orientation = orientation_from_normal(normal)

        grasp_pose = Pose(
            Position(
                float(center[0] + normal[0] * GRASP_OFFSET),
                float(center[1] + normal[1] * GRASP_OFFSET),
                float(center[2] + normal[2] * GRASP_OFFSET),
            ),
            orientation,
        )
        pre_grasp_pose = Pose(
            Position(
                float(center[0] + normal[0] * PRE_GRASP_OFFSET),
                float(center[1] + normal[1] * PRE_GRASP_OFFSET),
                float(center[2] + normal[2] * PRE_GRASP_OFFSET),
            ),
            orientation,
        )

        poses.append((pre_grasp_pose, grasp_pose))

    return poses


def orientation_from_normal(normal: tuple[float, float, float]) -> Orientation:
    """Surface normal -> TCP orientation."""

    nx, ny, nz = normalize_vector(normal)
    z_axis = (-nx, -ny, -nz)

    helper = (0.0, 0.0, 1.0)
    if abs(dot(z_axis, helper)) > 0.95:
        helper = (0.0, 1.0, 0.0)

    x_axis = normalize_vector(cross(helper, z_axis))
    y_axis = cross(z_axis, x_axis)

    return quaternion_from_axes(x_axis, y_axis, z_axis)


def quaternion_from_axes(
    x_axis: tuple[float, float, float], y_axis: tuple[float, float, float], z_axis: tuple[float, float, float]
) -> Orientation:
    """TCP axes -> quaternion."""

    m00, m01, m02 = x_axis[0], y_axis[0], z_axis[0]
    m10, m11, m12 = x_axis[1], y_axis[1], z_axis[1]
    m20, m21, m22 = x_axis[2], y_axis[2], z_axis[2]

    trace = m00 + m11 + m22

    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        x, y, z, w = (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        x, y, z, w = 0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        x, y, z, w = (m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        x, y, z, w = (m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s

    return normalize_orientation(Orientation(x, y, z, w))


def normalize_vector(v: tuple[float, float, float]) -> tuple[float, float, float]:
    norm = math.sqrt(dot(v, v))
    if norm == 0.0:
        raise ValueError("Invalid zero vector.")
    return (v[0] / norm, v[1] / norm, v[2] / norm)


def normalize_orientation(q: Orientation) -> Orientation:
    norm = math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w)
    if norm == 0.0:
        raise ValueError("Invalid quaternion.")
    return Orientation(q.x / norm, q.y / norm, q.z / norm, q.w / norm)


def cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def candidate_sort_key(candidate: tuple[Pose, Pose]) -> tuple[float, float, float, float]:
    pre_grasp_pose, grasp_pose = candidate

    return (
        -grasp_pose.position.z,
        abs(grasp_pose.position.y),
        abs(grasp_pose.position.x),
        distance_from_origin(pre_grasp_pose),
    )


def distance_from_origin(pose: Pose) -> float:
    return math.sqrt(
        pose.position.x * pose.position.x + pose.position.y * pose.position.y + pose.position.z * pose.position.z
    )
