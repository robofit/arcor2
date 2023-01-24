# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.7.0] - 2023-04-19

### Changelog

- App is refactored and adds endpoints for tracking user using body-tracking api
- App can track user in numerous ways:
    - Get user positions
    - Get user velocity and direction
    - Check how many users are in frame
    - Get RGB, depth and rgb with skeleton image
    - Show what camera sees in browser
    - Check if user is nearby some point
- **Breaking**: App runs in docker only in MOCK mode

## [0.6.0] - 2023-03-07

### Changed

- Health check end-point at `/healthz/ready`.
- Requires `pose` in the body of `GET /state/start`.

### Added

- New endpoint `GET /state/pose`.

## [0.5.0] - 2022-10-28

### Changed

- **BREAKING**: Implement new error handling flow. Error codes of **every** endpoint were replaced with error
  types as described in swagger documentation.
- Changed service name.
- Switched to Python 3.10, updated dependencies.

## [0.4.0] - 2021-10-25

### Changed

- New environment variable `ARCOR2_KINECT_AZURE_MOCK`.

### Fixed

- Depth file was not packaged (used in mock mode).

## [0.3.0] - 2021-05-21

### Changed

- Lazy import of `pyk4a` - mock can run without it.

## [0.2.0] - 2021-02-08

### Changed

- Mock now sends real images.
- Part of the code refactored into `arcor2/flask.py`.

## [0.1.0] - 2020-12-14

### Changed

- Initial release of the package.