# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),


## [0.8.0] - 2020-09-24
### Changed
- Initial release of the separated package.
- Execution service is now ok with packages that do not contain scene/project/package.json.
- Execution service now sends PackageChanged events (on: new, rename, delete).
- New environment variable: ARCOR2_EXECUTION_URL (defaults to 'ws://0.0.0.0:6790').
- Main script now don't have to be executable and contain shebang.