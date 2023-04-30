# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [1.0.1] - 2023-04-24

### Added

- Classes needed to import Kinect object type

## [1.0.0] - 2023-02-14

### Changed

- Dependency on arcor2 1.0.0.
- Compatibility with the newest version of the Project service.
- ARServer now also talks to Asset service (checks whether mesh/URDF exists).

## [0.27.0] - 2022-12-12

### Changed

- Dependency on `arcor2~=0.26.0`.

## [0.26.0] - 2022-10-28

### Changed

- Switched to Python 3.10, updated dependencies.

## [0.25.0] - 2022-08-17

### Changed

- Adaptation to changes in API of the Build service.
- Updated scene client (changed API).

## [0.24.0] - 2022-04-25

### Added

- New RPCs `GetScene` and `GetProject`.

## [0.23.0] - 2022-01-25

### Changed

- Breaking change of WebSockets API (`ActionStateBefore` event).
- Switched to Python 3.9, updated dependencies.

## [0.22.1] - 2021-10-26

### Changed

- Added HTTP upload server for logs from AREditor
  - Logs are uploaded to /root/logs (could be changed using ARCOR2_AREDITOR_LOGS_FOLDER env variable)

## [0.22.0] - 2021-10-25

### Changed

- When getting pose/joints from a robot fails, continue trying instead of giving up.
- Handle `KinematicsException` to deliver a more precise error message.
- Updating object models.
  - New RPC `UpdateObjectModel`.
  - Ability to lock individual ObjectTypes.
  - Various improvements regarding locking.
- Proper handling of scene/project problems.
  - Any problem makes scene/project invalid, and then it can't be opened.  
  - Scene/project problems are now checked when:
    - Scene/project is listed.
    - Opening a scene/project is requested.
  - Found problems are cached for better performance.
  - ObjectTypes are checked for changes during each listing of scenes/projects.
- Deleting ObjectTypes reworked.
  - `DeleteObjectType` replaced with `DeleteObjectTypes`.
  - The new RPC takes list of ObjectType IDs.
  - Empty list means all ObjectTypes.
  - It returns list of id/error for types that could not be removed.
  - This is especially useful for usage with `dry_run`.
- Updated environment variables, please see README.
- Improved logging to debug 'Locking failed'.
- Support for virtual collision objects.
  - `AddVirtualCollisionObjectToScene` RPC creates a new OT and adds its instance to a scene.
  - In the simplest case, each collision object will have its own ObjectType.
  - But it is also possible to add more instances as with other types.
  - When the last instance of VCO is removed, ARServer also removes the ObjectType automatically.
- Ignoring `hidden` actions (a new flag in `ActionMetadata`).
- New RPC `ObjectTypeUsage` returning scene ids where the ObjectType is used.
- Support for debugging - relaying related RPCs to the Execution Service.
- Better handling of exceptions in asyncio tasks.
  - More useful traceback is printed out.
  - In development mode, an unhandled exception leads to shutdown of a service.
  - In production mode, traceback is printed out and the service tries to continue.

### Fixed

- Ban HT mode changes while moving.
- Arguments for getting robot joints (only affected multi-arm robots).
- Handle locking exceptions on scene start/stop.
- Copying of action points.
  - Fixed locking within `CopyActionPoint`.
  - Fixed update of orientation IDs.
- Added locking to Project client to make the cache caching properly.
- `modified`  was missing for disabled object.
  - This happened when it was not possible to get object's base.
- Copy AP - update of orientation ID in actions.
- Removed 'delayed' unlocking of resources which caused race conditions in some cases and made the crashes hard to debug.
- HT mode for single arm robots was broken.


## [0.21.0] - 2021-08-05

### Changed

- Locks are not automatically released when aiming is done or cancelled.
- Linear movements are used by default for stepping and table alignment.
- Joints stream (`RobotJoints` event) now contains also gripper joints when available (depends on the particular ObjectType).

### Fixed

- Getting action results (the result was always `False`).
- `ctx_read_lock` made some RPCs impossible to success.
- Object parameters checking.
  - Values and types of object parameters were not checked at all.
  - For now, only basic types are supported.

## [0.20.0] - 2021-07-29

### Changed

- Support for multi arm robots.
  - Dealing with `arm_id` parameter in RPCs.
  - Streaming EEF poses for all arms.
- Allow to reposition scene objects while online.
  - It was allowed to reposition objects using robot,
  - ...but disallowed to do it manually.
  - This was inconsistent and unnecessarily restrictive.
  - Now objects (except robots) can be repositioned anytime.
- When creating a new project, common parameters are added automatically.
  - At the moment those are `scene_id` and `project_id`.
  - A user could use or remove them.
- Collisions are not removed after stopping the scene.
- ObjectType change detection is now based on `modified` instead of comparing source codes.
- ARServer Project service client now stores cached scenes/projects.
- Object aiming reworked.
  - RPCs were renamed and all of them now have `dry_run`.
  - There is a new method to cancel the process.
  - One user can be aiming one object at the moment.
  - Both the object and the selected robot have to be write-locked.
  - Improved logging.
  - Test was added.
- Server no longer downloads URDF packages.
  - `ARCOR2_DATA_PATH` environment variable is no longer used.
  - Clients will get URDFs through reverse proxy from Project service.
- `NewObjectType` no longer assumes that mesh already exists.
  - A file associated to mesh must exist in advance.
  
  
### Fixed
- All calls to the Scene service are guarded against exceptions.
- Renaming of project parameters fixed.
  - It was possible to use already taken name.

## [0.19.0] - 2021-06-22

- Update to API version 0.15.0.

## [0.18.0] - 2021-06-11

### Changed

- Updated to work with Project service 0.8.0.
- Allow fast re-login after connection was broken.
- Added locking to const-related RPCs.
- Log calibration-related errors.

### Fixed

- Handle invalid ObjectType settings annotation.

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
