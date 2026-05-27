# noqa: TAE001
# mypy: ignore-errors
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description() -> LaunchDescription:
    declared_arguments = [
        DeclareLaunchArgument("robot_ip"),
        DeclareLaunchArgument("use_mock_hardware", default_value="false"),
        DeclareLaunchArgument("mock_sensor_commands", default_value="false"),
        DeclareLaunchArgument(
            "initial_joint_controller",
            default_value="scaled_joint_trajectory_controller",
        ),
        DeclareLaunchArgument("activate_joint_controller", default_value="true"),
    ]

    robot_ip = LaunchConfiguration("robot_ip")
    use_mock_hardware = LaunchConfiguration("use_mock_hardware")
    mock_sensor_commands = LaunchConfiguration("mock_sensor_commands")
    initial_joint_controller = LaunchConfiguration("initial_joint_controller")
    activate_joint_controller = LaunchConfiguration("activate_joint_controller")

    ur_control = "/opt/ros/jazzy/share/ur_robot_driver/launch/ur_control.launch.py"
    custom_rsp = str(Path(__file__).resolve().parent / "custom_rsp.launch.py")

    base_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ur_control),
        launch_arguments={
            "ur_type": "ur5e",
            "robot_ip": robot_ip,
            "use_mock_hardware": use_mock_hardware,
            "mock_sensor_commands": mock_sensor_commands,
            "initial_joint_controller": initial_joint_controller,
            "activate_joint_controller": activate_joint_controller,
            "description_launchfile": custom_rsp,
        }.items(),
    )

    return LaunchDescription(declared_arguments + [base_launch])
