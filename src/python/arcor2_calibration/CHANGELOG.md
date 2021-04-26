# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.5.0] - WIP
### Changed
- `PUT /calibrate/camera` now returns `EstimatedPose` (pose + quality).

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
