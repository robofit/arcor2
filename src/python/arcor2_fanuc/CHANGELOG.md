# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.2.0] - 2022-07-01

### Changed

- **BREAKING**: Implement new error handling flow. Error codes of **every** endpoint were replaced with error 
  types as described in swagger documentation.

- Update API description.

### Added

- New exception classes

## [0.1.0] - 2022-05-23

### Added
- Initial release of the Fanuc Service - REST API based on `fanucpy` library.
- The package also contains universal ObjectType and a URDF model for LRMate 200iD/7L (adapted from ROS Industrial).
