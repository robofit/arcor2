# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.11.0] - 2021-02-08

### Changed
- `Calibration` RPC renamed to `GetCameraPose`.
- New `MarkersCorners` RPC.

## [0.10.0] - 2020-12-14

### Changed
- `ActionResult` event changed to match with `ActionState` (support for actions that may return more than one result).
- `ProcessState` event for signalling state of long-running processes.
- RPCs for camera/robot calibration.

### Changed
- RPC for IK/FK.

## [0.9.2] - 2020-10-30

### Changed
- RPC for IK/FK.


## [0.9.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.9.0] - 2020-10-16

### Changed
- WS API for updates of scene objects parameters and management of project-defined overrides.
- `UpdateObjectPose` and `UpdateActionPointPosition` now has dry_run.
- Box/Cylinder/Sphere models now have some constraints on their dimensions (checked in `__post_init__`).

## [0.8.0] - 2020-09-24
### Changed
- The first release of the separated package.
