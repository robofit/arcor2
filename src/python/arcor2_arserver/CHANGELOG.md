# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.13.0] - 2021-03-03

### Changed

-  API to copy action point (including orientations, joints, child APs).
- Robot-related API (MoveToPose, MoveToJoints, MoveToActionPoint) updated in order to contain `safe` parameter.
- API to enable/disable robot hand teaching mode.  
- Concrete and helpful error messages when a name entered by the user is refused.

### Fixed
- Only `BareActionPoint` was sent on parent change.

## [0.12.0] - 2021-02-08

### Changed
- Improved scene-related messages.
  - Error messages now contain the name of the object which caused the error.
- New `MarkersCorners` RPC for getting markers corners.
- Support for `an` parameter (explicit parameters).
- Improved check of action signature and annotation.
- New WS API for execution state reporting.
- Support for project constants.
  - Only basic types are supported so far.

### Fixed
- Better handling of missing collision model.
  - If server can't get collision model of the object, the object is disabled.
  - Previously, this situation caused crash of the server.
- `GetCameraPose` callback fixed (used to be `Calibration`).

## [0.11.0] - 2020-12-14

### Changed
- Improved support for logic branching.
  - So far, only boolean outputs are supported.
- Improved handling of return values (uses the same function as the main script).
- The internal database of ObjectTypes in updated each time before opening a scene or a project.
  - Changes are notified using `ChangedObjectTypes` event (one event for added objects, one for updated and another one for deleted ones).
- Support for camera/robot calibration.
- Initial support for cameras (getting images, camera parameters).

## [0.10.1] - 2020-10-30

### Changed
- RPC for IK/FK.

## [0.10.0] - 2020-10-22

### Changed
- Updated due to a breaking change in `arcor2_execution_data`.

## [0.9.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

### Fixed
- fixed check for existing override
 
## [0.9.0] - 2020-10-16

### Changed
- WS API for updates of scene objects parameters and management of project-defined overrides.
- Integration tests refactored into multiple modules that can run in parallel.
- `UpdateObjectPose` and `UpdateActionPointPosition` now has dry_run.
- Box/Cylinder/Sphere models now have some constraints on their dimensions.
- 

## [0.8.0] - 2020-09-24
### Changed
- The first release of the separated package.
- RPC/Events refactored. 
- ARServer script now has ```--openapi``` argument and is able to generate OpenAPI models for RPCs and events.
- Detection of loops in: AP hierarchy, logic.
- Caching client for Project service.
- Proper handling of object inheritance.
- ObjectTypes are stored in temporary module on disk.
- Integration tests.
