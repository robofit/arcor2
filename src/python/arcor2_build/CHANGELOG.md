# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.11.0] - 2021-02-08

### Changed
- Part of the code refactored into `arcor2/flask.py`.
- Support for explicit parameters in the main script.
  - `Actions` class is no longer generated (does not make sense now). 
  - `Resources` class is no longer generated (used to have actions parameters as properties).
  - Improved/adapted `ActionPoints` generated class.
- Support for project constants (parameter type `constant`).
- An action can now use a previous result as its parameter (parameter type `link`).

## [0.10.0] - 2020-12-14

### Changed
- Ability to generate branched logic (if/elif block after action).

## [0.9.2] - 2020-10-30

### Changed
- ARCOR2 dependency updated

## [0.9.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.9.0] - 2020-10-16

### Changed
- Code generation adapted according to `print_exception` location change.

## [0.8.1] - 2020-10-05

### Added
- Build now has `--debug` argument ([0e6e418](http://github.com/robofit/arcor2/commit/0e6e418)).
### Fixed
- Fixed empty response error ([0edc1a6](http://github.com/robofit/arcor2/commit/0edc1a6)).
### Changed
- Build now assembles the execution package in memory ([7ac70d0](http://github.com/robofit/arcor2/commit/7ac70d0)).

## [0.8.0] - 2020-09-24
### Changed
- The first release of the separated package.
