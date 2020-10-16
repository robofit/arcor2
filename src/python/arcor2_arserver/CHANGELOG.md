# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

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