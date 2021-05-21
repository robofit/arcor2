# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.17.0] - 2021-05-21

### Changed

- Return value of `GetCameraPose` RPC updated.
- Objects initialization order.
  - Object initialization order can be set using class-level `INIT_PRIORITY` variable.
  - The higher priority, the sooner are objects of that type initialized.
  - Initialization happens in parallel (for objects of the same priority).
- `SetEefPerpendicularToWorld` now calls IK in parallel.
  - This provides almost 100% speed-up even when the robot service proceeds requests one by one.
- Added locking of internal resources.
  - Created a lock module that allows to read/write lock existing or special objects. The module contains:
    - lock object with all necessary methods;
    - structures for keeping data about locked objects;
    - locking-related exceptions;
    - queue and task for notifying UI about lock data;
    - methods for auto-unlocking after timeout when user logouts.
  - Base tests of locking structure.
  - RPCs for (un)locking object, registering user name.
  - Events for (un)locking object.
  - Created a class for maintaining connected UIs.
  - Project methods to get object by ID, object parent and object children.
  
  - All RPCs that requires some kind of locking are now lock-guarded.
  - Updated existing tests to work with newly implemented locking.
  - Global variables `SCENE`, `PROJECT` and `INTERFACES` moved to new classes.
- Rewritten cache for the Project service.
  - The cache is now always on (provides a significant speed-up).
  - External updates to the Project service are recognized properly.
- New RPC `AddApUsingRobot`.
- Support for multiple inheritance.
    - ObjectTypes can now use mixins.
    - It should be used like `class NewObjectType(MixinA, MixinB, Generic)`.
    - E.g. the last ancestor should be something derived from `Generic`.
- `SetEefPerpendicularToWorld` faster as it calls IK in parallel. 

### Fixed

- `SceneState` event was not sent to a newly connected UIs.
- Results of actions are now forgotten when going offline.
- Fixed support for `link` parameter type.

## [0.16.0] - 2021-04-20

### Fixed
- Action can't use its own result as a parameter (link parameter type).

### Changed
- Dependency on arcor2 0.15.0 with updated REST client.
- Action parameter value is now always JSON.
  - It used to be a string for link/constant special types.


## [0.15.1] - 2021-04-19

### Fixed
- Dependency on bugfix release of arcor2.

## [0.15.0] - 2021-03-30

### Changed
- New RPC `SetEefPerpendicularToWorld`.
- New RPC `StepRobotEef`.

### Fixed
- `CopyActionPoint` RPC: update action parameters to use copied orientations.
- Scene now goes offline before execution and to the original state after it.
- Scene-related messages adapted to a new terminology.

## [0.14.0] - 2021-03-15

### Changed
- Improved logging for debugging robot features.
- Suffix is added to copied AP/action instead of prefix.

### Fixed
- Names for orientations/joints were not checked as valid identifiers.
- Action names were checked, but should not be.

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
