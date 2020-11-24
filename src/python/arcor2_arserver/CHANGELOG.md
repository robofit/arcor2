# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.11.0] - WIP

### Changed
- Improved support for logic branching.
  - So far, only boolean outputs are supported.
- Improved handling of return values (uses the same function as the main script).
- The internal database of ObjectTypes in updated each time before opening a scene or a project.
  - Changes are notified using `ChangedObjectTypes` event (one event for added objects, one for updated and another one for deleted ones).

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
