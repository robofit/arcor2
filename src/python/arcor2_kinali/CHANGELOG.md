# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

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
