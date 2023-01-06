# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [1.0.0] - WIP

### Changed

- Marked as a stable version.

## [0.6.0] - 2022-10-28

### Changed

- Switched to Python 3.10, updated dependencies.

## [0.5.1] - 2022-09-08

### Fixed

- `DobotGeneral` had wrong ancestor.
- `moveType` default value.

## [0.5.0] - 2022-09-02

### Changed
- **BREAKING**: Implement new error handling flow. Error codes of **every** endpoint were replaced with error 
  types as described in swagger documentation.
- Updated API description.
- Model and port are now set using environment variables.

### Added
- New exception classes

## [0.4.1] - 2022-02-17

### Added

- Support for safe movements.
  - Connection to Scene Service Mock needed.
  - New parameter `safe` for `PUT /eef/pose`.
  - For JOINT and JUMP movements: add intermediate points with higher z, if there might be a collision.
  - For LINEAR: raise an exception if there might be collision.
- Debug logging can be turned on by adding `-d` or setting `ARCOR2_DOBOT_DEBUG`.

### Fixed

- In mock-mode, `cleanup` was throwing `AttributeError`.

## [0.4.0] - 2022-01-25

### Added

- Support for conveyor belt.

### Changed

- Suction is switched off during `stop`.

## [0.3.0] - 2021-10-25

### Changed
 - New environment variable `ARCOR2_DOBOT_MOCK` to start the service in a mock mode.
 - Classes updated to match `Robot` (new argument `include_gripper`). 
 - Handle `DobotApi` exceptions to produce nice error messages.
 - Use HTTP code 204 instead of 200 where it makes sense.

## [0.2.3] - 2021-05-21

### Fixed
 - EEF orientation.
 - State controller paths.

## [0.2.2] - 2021-03-17

### Fixed
 - Suction offset for M1 adjusted

## [0.2.1] - 2021-03-15

### Fixed
 - Dobot axis Z is in mm
 - Added fixed offset for suction

## [0.2.0] - 2021-03-03

### Changed
- Integration of `pydobot` library (own modified fork).
- API for hand teaching mode.

## [0.1.0] - 2021-02-08

### Changed
- Initial release of the Dobot service.
