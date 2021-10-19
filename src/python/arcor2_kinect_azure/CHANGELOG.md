# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.4.0] - WIP

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