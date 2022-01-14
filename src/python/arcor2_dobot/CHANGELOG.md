# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.4.0] - WIP

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
