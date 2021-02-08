# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

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