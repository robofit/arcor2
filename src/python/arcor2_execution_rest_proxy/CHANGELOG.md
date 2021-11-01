# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.15.0] - WIP

### Changed

- Added API for setting and getting breakpoints.
  - Breakpoints are cleared when package is normally started or deleted.
  - Breakpoints can be only set when there is no running package.
- API version changed to 0.8.0.

## [0.14.0] - 2021-10-25

### Changed

- Support for debugging.
  - New methods `PUT /packages/{packageId}/debug` and `PUT /packages/step`.
  - The script can now be started in paused state.
  - Breakpoints can be set on action points.
  - The paused script can be stepped to the following action.

## [0.13.2] - 2021-09-02

### Changed
- Added EXPOSE to dockerfile

## [0.13.1] - 2021-08-04

### Fixed
- API version was not updated.

## [0.13.0] - 2021-07-29

### Changed
- Property `description` added to `SummaryProject`.
- If more exceptions happen, they are combined into `exceptionMessage`.


## [0.12.0] - 2021-06-11

### Changed
- OpenAPI definition updated.

## [0.11.0] - 2021-05-21

### Changed
- Update of dependencies.

## [0.10.0] - 2021-03-30

### Changed
- Implements Execution API 0.5.0.
  - Execution state `Pending` was added, which is reported when long-running operation takes place (e.g. pause a package).

## [0.9.0] - 2021-02-08

### Changed
- Part of the code refactored into `arcor2/flask.py`.
- Update of 3rd party dependencies.

## [0.8.3] - 2020-12-14

### Fixed
- Error code and message when attempting to delete a non-existent execution package. 

## [0.8.2] - 2020-10-22

### Changed
- Implements Execution API 0.4.0.
  - `ProjectName` property added to `SummaryPackage` model.

## [0.8.1] - 2020-10-19

### Changed
- ARCOR2 dependency updated

## [0.8.0] - 2020-09-24
### Changed
- The first release of the separated package.
- API version is now hardcoded (0.3.0 at the moment).
- Tokens controller added.
  - Tokens as saved in DB in directory specified by ```ARCOR2_EXECUTION_PROXY_DB_PATH```.
- Added wait until the Execution service is up.
