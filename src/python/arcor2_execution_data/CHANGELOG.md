# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.11.0] - WIP

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