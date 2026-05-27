# noqa: TAE001
# mypy: ignore-errors
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    package_root = Path(__file__).resolve().parents[1]
    urdf_path = package_root / "data" / "urdf" / "ur5e.urdf"
    meshes_dir = package_root / "data" / "urdf" / "meshes"

    text = urdf_path.read_text(encoding="utf-8")
    text = text.replace(
        "package://meshes/",
        f"file://{meshes_dir.as_posix()}/",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("ur_type", default_value="ur5e"),
            DeclareLaunchArgument("robot_ip", default_value="xyz"),
            DeclareLaunchArgument("use_mock_hardware", default_value="true"),
            DeclareLaunchArgument("mock_sensor_commands", default_value="false"),
            DeclareLaunchArgument("headless_mode", default_value="false"),
            DeclareLaunchArgument("kinematics_parameters_file", default_value=""),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                output="screen",
                parameters=[{"robot_description": text}],
            ),
        ]
    )
