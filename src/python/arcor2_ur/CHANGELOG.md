# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [1.4.1] - 2024-11-21

### Fixed

- Checking for robot's state - it should no longer be necessary to start the robot manually (before calling `PUT /state/start`). It should also work if the robot is already started.

## [1.4.0] - 2024-11-06

### Changed

- Ability to control OnRobot VGC10 suction through Modbus (requires [RS485 URCap](https://github.com/UniversalRobots/Universal_Robots_ToolComm_Forwarder_URCap) in the robot).
- `ROBOT_IP` env. variable changed to `ARCOR2_UR_ROBOT_IP`.
- `PUT /state/start` often failed because robot was not yet ready to start a program - added check for robot's state - however, it does not work at the moment. Until it is resolved, it is recommended to start the robot manually.

## [1.3.0] - 2024-10-01

### Changed

- Docker image now checks for a robot calibration file at `/root/robot_calibration.yaml`. If not given, a default one is used.
- `ROBOT_CONTAINER_IP` was changed to `ROBOT_IP`.

## [1.2.1] - 2024-09-30

### Fixed

- ROS logger was not set to debug when requested by argument/environment variable (however, it has no effect on moveitpy).
- Parameter `velocity` not shown in Swagger UI.

## [1.2.0] - 2024-09-27

### Changed

- Update of ROS 2 dependencies.

## [1.1.0] - 2024-09-23

### Changed
- Removed waiting after trajectory execution (probably useless).
- Ability to set movement velocity and payload (mass only).

## [1.0.0] - 2024-09-12

### Changed
- Initial release of the UR service.
