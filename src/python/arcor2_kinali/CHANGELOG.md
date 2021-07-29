# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.15.0] - 2021-07-29

### Changed
- Implement `Search` service version `0.11.0`
- Implement `Robot` service version `0.12.0`
- All service now use `configurationId` instead of `configId`

## [0.14.0] - 2021-06-11

### Changed
- Implement `Interaction` service version `0.4.0`
- Update services version

## [0.13.1] - 2021-05-21

### Fixed
- `Aubo` had wrong XML child names for inverse kinematics call

## [0.13.0] - 2021-04-21

### Changed
- Class `AbstractRobot` updated for Robot 0.10.0
- Class `Aubo` (inverse_kinematics) updated for Robot 0.11.0

## [0.12.1] - 2021-03-15

### Fixed
- Getting suction IDs was broken.
- Fixed signatures of some robot methods.

### Changed
- Example scripts were updated with id-related changes.

## [0.12.0] - 2021-03-03

### Changed
- Parameter `safe` added to the `Robot` interface.
- Added an example using `RestHttpException`.

### Fixed
- `Simatic` robot was missing `move_to_joints` (moved to `AbstractRobot`).

## [0.11.1] - 2021-02-09

### Changed
- Add Ict service 0.1.0

## [0.11.0] - 2021-02-08

### Changed
- Added the mandatory `an` parameter to all actions.

### Fixed
- Invalid url in `move_relative_joints`.

## [0.10.0] - 2020-12-14

### Changed
- Class `KinaliRobot` divided into `Aubo` and `Simatic`.
- Added example of the main script using `Resources` class.
- Added URDF model for `Aubo`.
- Updated to for Robot 0.9.0, Search 0.7.0, Barcode 0.4.0.

## [0.9.2] - 2020-10-30

### Changed
- Call to `patch_object_actions` added to the example script.
- Slight change of `inverse_kinematics` method signature (`start_joints` and `avoid_collisions` now have default values).

## [0.9.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.9.0] - 2020-10-16
### Changed
- Clients updated to use rewritten `rest` module.
- KinaliRobot updated for Robot 0.8.0 (IK/FK methods added).
- Barcode, Robot and Search now have pose while Interaction and Statistic do not.

### Fixed
- Interaction/add_dialog now returns the selected option.
- Barcode: obsolete method `active_scanners` removed.

## [0.8.0] - 2020-09-24
### Changed
- Package is now part of the arcor2 monorepo.
- Update of ObjectTypes.
