# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.19.3] - 2021-11-15

## Fixed

- Improved handling of script/objects initialization failures (`arcor2_runtime`). 

## [0.19.2] - 2021-11-08

## Fixed

- Fixed mutual dependency between `arcor2_execution_data` and `arcor2_runtime` (`package.py` moved to `arcor2_runtime`).

## [0.19.1] - 2021-11-01

## Changed

- Updated dependency on arcor2_runtime

## [0.19.0] - 2021-10-25

### Changed

- Make RPCs less blocking.
- New environment variables `ARCOR2_EXECUTION_DEBUG` and `ARCOR2_EXECUTION_ASYNCIO_DEBUG` (see README for details).
- Added dependency on `3rdparty:websocket-client` to make `LoggingMixin` work.
- Support for debugging.
  - The script can now be started in paused state.
  - Breakpoints can be set on action points.
  - The paused script can be stepped to the following action.
- Better handling of exceptions in asyncio tasks.
  - More useful traceback is printed out.
  - In development mode, an unhandled exception leads to shutdown of a service.
  - In production mode, traceback is printed out and the service tries to continue.
- Relaying events with EEF poses/joints from the main script to the clients.
  - The script streams those by default for all robots. For mode details, please see README of `arcor2_runtime`. 

## [0.18.1] - 2021-09-02

### Changed
- Added EXPOSE to dockerfile


## [0.18.0] - 2021-08-05

### Changed

- Dependency on `arcor2==0.20.0` where `Robot` API changed.


## [0.17.0] - 2021-07-29

### Changed

- More stuff is now done asynchronously.
- Listing packages is now done in parallel.
- Improved logging (more events are logged).

### Fixed

- Exceptions were sometimes not reported.

## [0.16.0] - 2021-06-14

### Changed
- Dependency on `arcor2` 0.18.0.
- Dependency on `arcor2_execution_data` 0.11.0.

## [0.15.0] - 2021-06-14

### Changed
- Dependency on `arcor2` 0.17.0 (`constants` renamed to `parameters` in the `Project` model).

## [0.14.0] - 2021-05-21

### Changed
- Dependency on arcor2 0.16.0 (updated `Resources` class).

## [0.13.0] - 2021-04-20

### Changed
- Dependency on arcor2 0.15.0 with updated REST client.

## [0.12.0] - 2021-03-30

### Changed
- Dependency on arcor2 0.14.0.
- Reporting `paussing` before `paused` and `stopping` before `stopped`. 

### Fixed
- Script was stopped using a wrong signal.
  - Execution used SIGTERM instead of SIGINT.
  - Because of this, the script was not stopped gracefully.

## [0.11.1] - 2021-03-15

### Fixed
- Script was stopped using wrong signal (SIGTERM instead of SIGINT).
  - Because of this, the script was not stopped gracefully and `cleanup` methods of objects were not executed.

## [0.11.0] - 2021-02-08

### Changed
- Execution state reporting was improved
  - 'CurrentAction' and 'ActionState' events -> 'ActionStateBefore' and 'ActionStateAfter'.
  - 'ActionStateBefore' contains action id and its parameters.
  - 'ActionStateAfter' contains action id and its results.
  - 'PackageState' RPC removed.

## [0.10.0] - 2020-12-14

### Changed
- ARCOR2 dependency updated.

## [0.9.0] - 2020-10-22

### Changed
- Sets `project_meta` property of `PackageSummary` if the execution package contains `project.json` file.


## [0.8.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.8.0] - 2020-09-24
### Changed
- Initial release of the separated package.
- Execution service is now ok with packages that do not contain scene/project/package.json.
- Execution service now sends PackageChanged events (on: new, rename, delete).
- New environment variable: ARCOR2_EXECUTION_URL (defaults to 'ws://0.0.0.0:6790').
- Main script now don't have to be executable and contain shebang.
