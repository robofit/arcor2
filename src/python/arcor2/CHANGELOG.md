# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.12.1] - 2021-03-08

### Fixed
- `Pose` parameter plugin fixed to generate correct code in a case when action on action point A uses orientation from action point B.

## [0.12.0] - 2021-03-03

### Fixed
- Parameter plugins now return copy of the parameter in order to prevent changes in the project if the value is modified e.g. within an action.
- Method `update_project_sources` of the Project service client was fixed.

### Changed
- Flask-based apps now don't log each API call by default.
  - It can be turned on by setting `ARCOR2_REST_API_DEBUG`.
- The `rest` module has a new exception type RestHttpException for getting HTTP error codes.
- `is_valid_identifier` now behaves the same as `is_valid_type`, it does not insist on convention (PascalCase vs snake_case) and provides concrete error messages.
- `Robot` API now has `safe` parameter.
- `Robot` now has API for hand teaching mode.  
- Line length of generated code changed from 80 to 120.

## [0.11.1] - 2021-02-09

### Fixed
- `@action` decorator fixed.
- `KeyError` was raised when `an` parameter was not given to an action.
- This only happened in the "manual" script writing scenario and when `patch_object_actions` was used.

## [0.11.0] - 2021-02-08

### Changed
- Explicit action parameters.
  - `Resources` class now do not need to deal with parameters.
  - Update of ObjectTypes (all actions now have the mandatory `an` parameter).
- `CurrentAction` removed, `ActionState` divided into `ActionStateBefore` and `ActionStateAfter`.
- New module with shared code for Flask-based apps.
- Updates of 3rd party dependencies.
- WS server now logs too long RPCs. 
  - Max. duration could be configured using `ARCOR2_MAX_RPC_DURATION`.

### Fixed
- At a startup, the main script now checks if the scene is running before attempt to stop it.
- `image_from_str` function fixed.

## [0.10.0] - 2020-12-14

### Changed
- `action` decorator now handles outputs of actions.
- `CachedProject` has new methods for handling project logic.
- `ActionState` event now contains action results.
- New built-in ObjectTypes `RandomActions`.
- Parameter plugins slightly reworked, some new helper functions.
- If a robot has URDF, it is zipped and uploaded to the Project service).
  - ...as a mesh file, which is workaround for missing storage of URDF models.
- Scene service client updated to support version 0.4.0.
- New built-in abstract ObjectType `Camera`.
- Initial support for loading of URDF files.
- Some first tests for parameter plugins were added.

## [0.9.2] - 2020-10-30

### Fixed
- `parse` function now also catches `ValueError` exception.
-  `check_object_type` now tries to parse whole module instead of just source of the class itself.

### Changed
- `Robot` base class now have methods for IK/FK.
- It is possible to use `==` on `Position` instances.

## [0.9.1] - 2020-10-19

### Fixed
- package_version was ignoring `package` argument

## [0.9.0] - 2020-10-16

### Changed
- Scene client updated for Scene 0.3.0.
- Exceptions refactored (BREAKING).
  - Arcor2Exception no longer has `message` property
  - There is a new package arcor2/exceptions.
  - Clients using `handle` decorator now have specific error messages defined.
  - Previously generated execution packages will become broken as `print_exception` function was moved 
- Loggers are now created using functions from `logging` module.
- `rest` module rewritten (BREAKING).
  - Now there is only one method `call` which takes http method as an argument.
  - There is `ARCOR2_REST_DEBUG` environment variable. When set, debugging logs are turned on.

### Fixed
- JSON containing only boolean value was not handled properly by `arcor2.rest` module.


## [0.8.0] - 2020-09-24
### Changed
- Reorganisation of the repository - switched to monorepo based on [Pants](https://www.pantsbuild.org/docs/welcome-to-pants). The code was divided into more packages (that can be separatelly relased) within one repository.
- Tests now run on GitHub instead of CircleCi.
- Unification of objects and services
  - There is ```Generic``` base class for objects without pose, ```GenericWithPose``` for objects with pose and ```Robot``` class that should be base class for every robot.
- Integration of scene service (0.2.0).
- @action decorator is now added automatically in the run-time.
- ```Orientation``` dataclass now performs quaternion normalization in ```__post_init__```.
- ```Robot``` base class now has ```_move_lock``` mutex to ensure that only one move-action is called at the time.

## [0.8.0rc2] - 2020-09-16

## [0.8.0rc1] - 2020-09-15

## [0.8.0b8] - 2020-08-21
### Fixed
- Some robot-related issues fixed

## [0.8.0b7] - 2020-08-12
### Changed
- Scene service client: 'upsert_collision' now has optional 'mesh_parameters': parameter.

## [0.8.0b6] - 2020-08-03
### Changed
- New logic representation
- Unification of objects and services
- Integration of scene service

## [0.7.1] - 2020-07-15
### Fixed
- Fix of broken python package arcor2 0.7.0

## [0.7.0] - 2020-07-15
### Changed

- ARServer: new RPC 'TemporaryPackage'
- ARServer: RPC ObjectTypesChangedEvent renamed to ChangedObjectTypesEvent, now contains changed ObjectTypes meta instead of just type names
- ARServer: ShowMainScreenEvent.
- Package name added to PackageInfoEvent
- ARServer now compares its API_VERSION with API_VERSION of the Execution.
- ARServer: ShowMainScreenEvent will now not contain 'highlight' when sent to a newly connected UI.
- AP can now have another AP as parent
- rest: OptionalData now may contain list of primitive type.
- Execution: PackageStateEvent now contains package_id
- Execution: added 'executed' to PackageMeta

## [0.6.0] - 2020-06-19
### Changed

- Build/Execution proxy: allow port change using env. var.
- ARServer: RenameScene RPC now checks if scene name is unique and 'dry_run' works.
- ARServer: ListScenes/ListProjects now contain 'modified'.
- ARServer: DeleteObjectType RPC added.
- @action decorator is now compatible with Windows.
- Service class now has 'cleanup' method which is called when scene is closed or when script ends. Call of 'cleanup' can be disabled by 'export ARCOR_CLEANUP_SERVICES=False' - this is particularly useful when running the script manually again and again.
- Cleanup method for ObjectTypes.

## [0.5.1] - 2020-06-04
### Fixed
- ignoring check of return parameters
- allowing list of strings as request body

## [0.5.0] - 2020-06-01
### Changed
- ARServer container need to setup new env variable using docker-compose -> ARCOR2_DATA_PATH=/root/data
- ListProjects RPC now gets projects in parallel.
- dry_run parameter for selected RPCs
- EEF pose/robot joints streaming
- OpenScene, OpenProject, SceneClosed, ProjectClosed events.
- Execution proxy: use persistent websocket connection.
- SceneCollisionsEvent merged into PackageInfoEvent
- ARServer: RPC to cancel action execution.
- Execution package now contains package.json with its metadata. Execution service now supports renaming of packages.

## [0.4.3] - 2020-05-22
### Changed
- added support for CORS

## [0.4.2] - 2020-04-27
### Fixed
- Fix of functions to transform relative poses to absolute and vice versa

## [0.4.1] - 2020-04-22
### Added
- New RPCs for getting robot joints and effector pose
- New RPC to get IDs of EE and suctions
- Added pivot enum for UpdateObjectPoseUsingRobot

### Fixed
- Fix of remove action RPC
- Another fixes


## [0.4.0] - 2020-04-17
### Changed
- Complete redesign of RPC for ARClients (AREditor atm)
- Documentation of execution and build API
- Support for project service 0.2.0
- New and updated events
- Enhanced error messages
- Create (global) session to enable reuse of connections.

## [0.3.0] - 2020-03-24
### Changed
- Renamed RobotJoints to ProjectRobotJoints and ModelTypeEnum to Model3dType
- Added new services for Time and Logic related actons
- Added boolean parameter plugin
- Description, returns and origins fields marked as optional
- New event - ActionResult
- Separated script enabling discovery through UDP broadcast
- Support for list params
- Services and Action objects are now marked as disabled when some problem occured and error message is passed to GUI (previously such services/objects were ignored)
- Services with no configuration are disabled

## [0.2.1] - 2020-02-28
### Fixed
- Added compatibility with Project service v 0.1.1
- Param values and defaults are strings now
- min, max stored in extra as JSON string

## [0.2.0] - 2020-02-20
### Changed
- ExecuteAction RPC.
- Uuid for action object/point/action.
- Execution proxy PUT method
- ActionPoint class in execution package
- Removed loop in main script, when hasLogic == false
- Parameter values not send in currentAction event
- ProjectState RESUMED removed
- Execution: print out script output if not JSON.
- Joint: rotation -> value


## [0.1.7] - 2019-12-24
### Fixed
- Build: disable caching

## [0.1.5] - 2019-12-22
### Fixed
- Parameter plugins

## [0.1.4] - 2019-12-18
### Fixed
- Parameter of type relative_pose now accepts json string as value

## [0.1.3] - 2019-12-18
### Fixed
- N/A

## [0.1.2] - 2019-12-17
### Fixed
- bump docker version

## [0.1.1] - 2019-12-17
### Fixed
- bump docker version

## [0.1.1] - 2019-12-12
### Fixed
- N/A

## [0.1.0] - 2019-12-12
### Changed
- Separation of services.
