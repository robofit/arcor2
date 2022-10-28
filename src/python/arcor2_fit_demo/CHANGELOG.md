# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.11.0] - 2022-10-28

### Changed

- Switched to Python 3.10, updated dependencies.

## [0.10.1] - 2022-09-15

### Fixed

- Default url was missing for `ConveyorBelt`.

## [0.10.0] - 2022-09-02

### Changed

- No need to enter the Dobot model/port - both are now set when starting the service.

## [0.9.1] - 2022-08-29

### Changed

- Fixed upload of URDF files (`arcor2`).


## [0.9.0] - 2022-02-17

### Changed

- `pick` and `place` actions now have `safe_approach`, `safe_pick`/`safe_place` and `velocity` parameters.  

## [0.8.0] - 2022-01-25

### Added

- Support for Dobot conveyor belt.
  - There is a new Object Type `ConveyorBelt`.
  - The `url` in settings should point to the Dobot service (same url as for `DobotMagician`).

## [0.7.0] - 2021-10-25

### Changed

- Changes regarding updated signatures of `Robot` methods (`__init__`, `move_to_pose`, `robot_joints`).
- Kinect mesh fixed (some empty geometries removed).
- Dobot Magician materials removed from URDF.

## [0.6.1] - 2021-07-29

### Changed

- Default values for url fields of object parameters.
- Added docstrings to some actions.
- Added mesh for KinectAzure.

## [0.6.0] - 2021-05-21

### Changed

- Object types now use a mixin to share the common code.

### Fixed

- State controller paths are now consistent.

## [0.5.2] - 2021-03-30

### Fixed
- Dobot M1 does not have IK/FK so far

## [0.5.1] - 2021-03-15

### Fixed
- Signatures of some robot methods.
- Added temporal workaround to `AbstractDobot/pick`.

## [0.5.0] - 2021-03-03

### Changed
- `pick`/`place` actions.
- Hand teaching mode.
- During initialization, stop the Dobot service if already started.
- Raise exception on `safe=True` (not supported).

## [0.4.0] - 2021-02-08

### Changed
- ObjectTypes are now just proxies to the Dobot service.
- Added the mandatory `an` parameter to all actions.

### Fixed
- Dobot M1 model (rotation of parts).

## [0.3.0] - 2020-12-14

### Changed
- Various fixes regarding `DobotMagician` and `DobotM1`.
- `KinectAzure` ObjectType was added.

## [0.2.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.2.0] - 2020-09-24
### Changed
- Package is now part of the arcor2 monorepo.
- Support for Dobot M1.
- Improved handling of exceptions.
