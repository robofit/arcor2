# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [1.4.1] - 2025-05-06

### Fixed

- Avoided high CPU load when running under Docker Compose without stdin attached.
  The `select` call returned immediately due to detached stdin, causing a busy loop. 
  Now the stdin command thread is only started when stdin is a TTY.

## [1.4.0] - 2024-08-14

### Added

- There are optional callbacks for pause and resume events in the `action.Globals`.

## [1.3.0] - 2024-06-14

### Changed

- It is now possible to run actions in threads.

### Fixed

- It was not possible to use `Pose` as a breakpoint.

## [1.2.0] - 2024-04-11

### Changed

- Updated dependencies, switched to Python 3.11.

## [1.1.0] - 2024-01-08

### Changed

- Parameter `interact_with_scene_service` added to the `Resources` class.

## [1.0.0] - 2023-02-14

### Changed

- `ResourcesException` - `__context__` is now set to a first exception occurred during script initialization.
  - All exceptions that occurred during parallel initialization are still available in the `exceptions` array.

### Added

- `Resources` class has a `scene_start_timeout` argument which is handed over to the Scene client.

## [0.5.0] - 2022-12-12

### Changed

- Dependency on `arcor2~=0.26.0`.

## [0.4.0] - 2022-10-28

### Changed

- Switched to Python 3.10, updated dependencies.

## [0.3.2] - 2022-08-17

## Changed

- Update of scene client.

## [0.3.1] - 2022-08-15

## Changed

- Updated dependencies to match the released `arcor2` package.

## [0.3.0] - 2022-01-25

## Changed

- `@action` decorator updated to work with updated `ActionStateBefore`, where all properties are now optional.
  - Moreover, it now sends IDs of action points, that are used as parameters of actions, which is especially useful for projects without actions (actions are hand-coded).
- Switched to Python 3.9, updated dependencies.

## [0.2.2] - 2021-11-15

## Fixed

- Propagate error messages and related underlying exceptions when the initialization of objects fails.

## [0.2.1] - 2021-11-08

## Fixed

- Fixed mutual dependency between `arcor2_execution_data` and `arcor2_runtime` (`package.py` moved to `arcor2_runtime`).

## [0.2.0] - 2021-11-01
### Changed
- There is a new parameter `apply_action_mapping` allowing to disable application of action mapping.
    - This is useful for cases when actions are not defined in project.json.

## [0.1.0] - 2021-10-25
### Changed
- The first release of the package.
