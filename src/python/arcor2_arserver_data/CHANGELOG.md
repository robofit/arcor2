# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),


## [0.9.0] - 2020-10-16

### Changed
- WS API for updates of scene objects parameters and management of project-defined overrides.
- `UpdateObjectPose` and `UpdateActionPointPosition` now has dry_run.
- Box/Cylinder/Sphere models now have some constraints on their dimensions (checked in `__post_init__`).

## [0.8.0] - 2020-09-24
### Changed
- The first release of the separated package.