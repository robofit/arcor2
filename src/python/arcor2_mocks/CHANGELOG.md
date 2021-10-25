# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.17.0] - 2021-10-25

### Changed

- Dependency on `arcor2==0.21.0`.

### Fixed

- Handling of `created` property.

## [0.16.0] - 2021-07-29

### Changed

- Compatibility with Project service 0.10.0.
- Compatibility with Scene service 0.5.0.

## [0.15.0] - 2021-06-11

### Changed
- Updated to match API of Project service 0.8.0.

## [0.14.0] - 2021-05-21

### Changed
- Updated to match API of Project service 0.7.0.

## [0.13.0] - 2021-04-20

### Fixed
- Methods from System controller missed OpenAPI definition.

### Changed
- Configurable delay on start/stop.
  - Scene mock can simulate that start and stop take some time.
  - Mean time can be set using `ARCOR2_MOCK_SCENE_DELAY_MEAN`.
  - `ARCOR2_MOCK_SCENE_DELAY_SIGMA` sets the sigma of normal distribution.

## [0.12.0] - 2021-03-03

### Changed
- Methods to store/get mesh files were added to the mock Project.

## [0.11.0] - 2021-02-08

### Changed
- Part of the code refactored into `arcor2/flask.py`.
- Update of 3rd party dependencies.

## [0.10.0] - 2020-12-14

### Changed
- Scene service mock updated to match Scene 0.4.0.

## [0.9.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.9.0] - 2020-10-16
- Scene Service Mock updated to match Scene Service version 0.3.0. 

## [0.8.0] - 2020-09-23
### Changed
- Mocks updated to match Project 0.4.0 and Scene 0.2.0.