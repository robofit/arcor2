# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [1.0.0] - WIP

### Changed

- Marked as a stable version.
- Added dependency on `arcor2_runtime` (so a manually written script can import e.g. `ResourcesException`).
- Health check end-point changed to `/healthz/ready`.

## [0.25.0] - 2022-12-12

### Changed

- Dependency on `arcor2~=0.26.0`.

## [0.24.0] - 2022-10-28

### Changed

- Switched to Python 3.10, updated dependencies.

## [0.23.0] - 2022-07-08

### Changed

- **BREAKING**: Implement new error handling flow. Error codes of **every** endpoint were replaced with error 
  types as described in swagger documentation.

- **BREAKING**: `ProjectPublish` operation parameter `project_id` moved to query as `projectId`. 
  Error codes were replaced with error types as described in swagger documentation.

- Update of API description.

## [0.22.0] - 2022-02-04

### Changed

- Python 3.9.
- API version is now the same as service version.

## [0.21.0] - 2021-10-25

### Changed

- Published archive name.
  - The resulting zip name is `pkg_name_package.zip`.
  - Or `project_name_package.zip` when no package name is given.

## [0.20.0] - 2021-09-07

### Changed
- Updated `arcor2` dependency.
- New environment variable `ARCOR2_BUILD_DEBUG` - to turn on debugging output.

## [0.19.1] - 2021-09-02

### Changed
- Added EXPOSE to dockerfile

## [0.19.0] - 2021-07-30

### Changed
- Depending on `arcor2==0.20.0`.

### Fixed

- Package import failed in cases where files contained non-ascii characters.
  - The problem was in `arcor2.rest` module which was not encoding data properly.
- Scene/project `overWrite` flags were required all the time.

## [0.18.0] - 2021-07-29

### Changed

- Change constants to project parameters.

## [0.17.0] - 2021-06-14

### Changed
- Updated code generation for `Resources` (moved, now without parameters).

## [0.16.0] - 2021-06-11

### Changed
- OpenAPI definition updated.

## [0.15.0] - 2021-05-21

### Changed
- `overwrite` flag divided into: `overwriteScene`, `overwriteProject`, `overwriteObjectTypes`, `overwriteProjectSources`, `overwriteCollisionModels`.
- Action parameter value is always JSON.
  - It used to be just string for link/constant types.
  - Now it is always JSON to be more consistent.
- Support for multiple inheritance.
  - ObjectTypes can now use mixins.
  - It should be used like `class NewObjectType(MixinA, MixinB, Generic)`.
  - E.g. the last ancestor should be something derived from `Generic`.
- During a package import, object types used in a scene are checked whether they are not abstract.

## [0.14.1] - 2021-04-19

### Fixed
- Dependency on a bugfix release of arcor2.

## [0.14.0] - 2021-03-30

### Changed
- Considerably faster builds and imports.
- Allow unused actions.
- Import run returns `ImportedPackage` containing scene and project IDs.

## [0.13.0] - 2021-03-15

### Changed
- Dependency on arcor2 0.13.0.
- Generated `ActionPoints` class now returns copy of data (poses etc. can be freely modified within actions).


## [0.12.1] - 2021-03-08

### Fixed
- Bump dependency to arcor2 0.12.1 which fixes code generation in the `Pose` plugin.
- Check whether ObjectType id (class name) is the same as its models id.
  - The assertion was turned into exception.

## [0.12.0] - 2021-03-03

### Changed
- A new method `PUT /project/import` to import existing execution package.
  - Import fails if data already exists and there is any difference.
  - Import can be forced by setting `overwrite` parameter.

### Fixed
- Build now returns response messages in JSON.

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
