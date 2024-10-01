# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

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
