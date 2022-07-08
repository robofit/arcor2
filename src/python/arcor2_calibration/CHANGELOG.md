# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.8.0] - WIP

### Changed

- **BREAKING**: Implement new error handling flow. Error codes of **every** endpoint were replaced with error 
  types as described in swagger documentation.

## [0.7.0] - 2021-10-25

### Changed

- New environment variables: 
  - `ARCOR2_CALIBRATION_DEBUG` to turn on debugging.
  - `ARCOR2_CALIBRATION_MOCK` to start in mock mode.

## [0.6.1] - 2021-07-29

### Fixed

- Handle invalid input parameters (camera matrix).
- Scale down images to a common resolution before computing blur score.

## [0.6.0] - 2021-06-11
### Changed

- Improved quality estimation (take orientation into account).
- Reject blurry images.

## [0.5.0] - 2021-05-21
### Changed
- `PUT /calibrate/camera` now returns `EstimatedPose` (pose + quality).

### Fixed
- Command line arguments fixed.
  - It is mandatory to provide `-c` (path to a configuration file) or one of `-s` (prints OpenAPI) or `-m` (start as mock).

## [0.4.0] - 2021-04-26
### Changed
- The service now requires YAML configuration file where placement of markers is specified.
- There might be 1-n markers in an arbitrary pose.
- At least one of the configured markers should be visible.
- Un-configured markers are ignored.  
- Estimated poses of the camera from multiple detected markers are so far simply averaged.
- The average is weighted according to the camera-marker distance.

## [0.3.0] - 2021-03-30
### Changed
- `PUT /calibrate/camera` now has `inverse` parameter. 

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
