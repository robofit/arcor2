import rclpy  # pants: no-infer-dep
from rclpy.executors import ExternalShutdownException  # pants: no-infer-dep
from rclpy.node import Node  # pants: no-infer-dep
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy  # pants: no-infer-dep
from std_msgs.msg import Bool  # pants: no-infer-dep
from ur_dashboard_msgs.msg import RobotMode  # pants: no-infer-dep

from arcor2_ur.topics import ROBOT_MODE_TOPIC, ROBOT_PROGRAM_RUNNING_TOPIC


class PublisherNode(Node):
    def __init__(self) -> None:
        super().__init__("minimal_publisher")

        qos = QoSProfile(
            depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL, reliability=QoSReliabilityPolicy.RELIABLE
        )

        self.robot_program_running_pub = self.create_publisher(Bool, ROBOT_PROGRAM_RUNNING_TOPIC, qos)
        self.robot_mode_pub = self.create_publisher(RobotMode, ROBOT_MODE_TOPIC, qos)


def main() -> None:
    rclpy.init()
    publisher_node = PublisherNode()
    publisher_node.robot_program_running_pub.publish(Bool(data=True))
    publisher_node.robot_mode_pub.publish(RobotMode(mode=RobotMode.RUNNING))
    try:
        rclpy.spin(publisher_node)
    except ExternalShutdownException:
        # Happens when the process is terminated from the outside; exit cleanly.
        pass
    finally:
        publisher_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
