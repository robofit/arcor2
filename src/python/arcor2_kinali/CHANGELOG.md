# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## [0.9.0] - 2020-10-16
### Changed
- Clients updated to use rewritten `rest` module.
- KinaliRobot updated for Robot 0.8.0 (IK/FK methods added).
- Barcode, Robot and Search now have pose while Interaction and Statistic do not.

### Fixed
- Interaction/add_dialog now returns the selected option.
- Barcode: obsolete method `active_scanners` removed.

## [0.8.0] - 2020-09-24
### Changed
- Package is now part of the arcor2 monorepo.
- Update of ObjectTypes.