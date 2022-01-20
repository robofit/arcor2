# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.3.0] - WIP

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
