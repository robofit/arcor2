# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.2.0] - 2021-02-08
### Changed
- Part of the code refactored into `arcor2/flask.py`.
- API for getting pixel coordinates of markers corners.
  - Approx. three times faster than camera calibration.

## [0.1.1] - 2020-12-14
### Changed
- Bump version to allow reupload to pypi

## [0.1.0] - 2020-12-14
### Changed
- Initial release of the package.
- Support for camera calibration.
- Support for robot calibration.
  - URDF model of the robot needed.
  - Requires depth camera (e.g. Kinect).
- `--mock` argument to start the service in a simulation mode.