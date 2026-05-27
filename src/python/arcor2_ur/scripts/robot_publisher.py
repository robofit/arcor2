from importlib import resources

import rclpy  # pants: no-infer-dep
from geometry_msgs.msg import TransformStamped  # pants: no-infer-dep
from rclpy.executors import ExternalShutdownException  # pants: no-infer-dep
from rclpy.node import Node  # pants: no-infer-dep
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy  # pants: no-infer-dep
from std_msgs.msg import Bool  # pants: no-infer-dep
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster  # pants: no-infer-dep
from ur_dashboard_msgs.msg import RobotMode  # pants: no-infer-dep

from arcor2_ur.topics import ROBOT_MODE_TOPIC, ROBOT_PROGRAM_RUNNING_TOPIC


def load_robot_description() -> str:
    urdf_res = resources.files("arcor2_ur").joinpath("data/urdf/ur5e.urdf")
    meshes_res = resources.files("arcor2_ur").joinpath("data/urdf/meshes")

    text = urdf_res.read_text(encoding="utf-8")

    with resources.as_file(meshes_res) as meshes_dir:
        text = text.replace(
            "package://meshes/",
            f"file://{meshes_dir.as_posix()}/",
        )

    return text


def load_robot_description_semantic() -> str:
    srdf_res = resources.files("arcor2_ur").joinpath("data/urdf/ur5e.srdf")
    return srdf_res.read_text(encoding="utf-8")


class PublisherNode(Node):
    def __init__(self) -> None:
        super().__init__("arcor2_ur_test_robot_publisher")

        qos = QoSProfile(
            depth=1,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
        )

        self.robot_program_running_pub = self.create_publisher(Bool, ROBOT_PROGRAM_RUNNING_TOPIC, qos)
        self.robot_mode_pub = self.create_publisher(RobotMode, ROBOT_MODE_TOPIC, qos)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)

        self._publish_static_transforms()
        self.timer = self.create_timer(1.0, self._republish)

    def _publish_static_transforms(self) -> None:
        transforms = [
            self._transform("tool0", "suction_base_link", 0.0, 0.0, 0.0),
            self._transform("suction_base_link", "suction_cup_link", 0.0, 0.0, 0.1025),
            self._transform("suction_cup_link", "suction_tcp", 0.0, 0.0, 0.0),
        ]

        self.static_tf_broadcaster.sendTransform(transforms)

    def _transform(self, parent_frame: str, child_frame: str, x: float, y: float, z: float) -> TransformStamped:
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = parent_frame
        transform.child_frame_id = child_frame
        transform.transform.translation.x = x
        transform.transform.translation.y = y
        transform.transform.translation.z = z
        transform.transform.rotation.x = 0.0
        transform.transform.rotation.y = 0.0
        transform.transform.rotation.z = 0.0
        transform.transform.rotation.w = 1.0
        return transform

    def _republish(self) -> None:
        self.robot_program_running_pub.publish(Bool(data=True))
        self.robot_mode_pub.publish(RobotMode(mode=RobotMode.RUNNING))


def main() -> None:
    rclpy.init()
    publisher_node = PublisherNode()

    publisher_node._republish()

    try:
        rclpy.spin(publisher_node)
    except ExternalShutdownException:
        pass
    finally:
        publisher_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
