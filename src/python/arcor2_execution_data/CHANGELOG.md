# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [1.1.0] - 2024-01-03

### Changed

- Dependency on `arcor2_runtime~=1.1.0`.

## [1.0.0] - 2023-02-14

### Changed

- Marked as a stable version.

## [0.16.0] - 2022-10-28

### Changed

- Switched to Python 3.10, updated dependencies.

## [0.15.0] - 2022-01-25

### Changed

- Breaking change of WebSockets API (`ActionStateBefore` event).
- Switched to Python 3.9, updated dependencies.

## [0.14.1] - 2021-11-08

## Fixed

- Fixed mutual dependency between `arcor2_execution_data` and `arcor2_runtime` (`package.py` moved to `arcor2_runtime`).

## [0.14.0] - 2021-10-25

### Changed

- Stuff needed by the main script moved to `arcor2_runtime`.
- New RPC `StepAction`, debugging-related arguments added to `RunPackage`.

## [0.13.0] - 2021-08-05

### Changed

- `Resources` can now handle `CollisionObject`.


## [0.12.0] - 2021-07-29

### Changed

- Property `description` added to `ProjectMeta`.

## [0.11.0] - 2021-06-14

### Changed
- Modules `package` and `resources` moved here from `arcor2` package.
- `Resources` class now do not have any parameters (it used to have `project_id`).

### Fixed
- In `Resources/__exit__`, collision models were deleted before calling `cleanup` for each object.

## [0.10.0] - 2021-02-08

### Changed
- `PackageState` RPC removed.

## [0.9.0] - 2020-10-22

### Changed
- `PackageSummary` now contains optional `project_meta` property which may hold basic information about the project embedded in the execution package.

## [0.8.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.8.0] - 2020-09-24
### Changed
- The first release of the separated package.
