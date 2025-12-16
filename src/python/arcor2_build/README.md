# arcor2_build

## Environment variables

- `ARCOR2_BUILD_URL=http://0.0.0.0:5008` - by default, the service listens on port 5008.
- `ARCOR2_BUILD_DEBUG=1` - switches logger to the `DEBUG` level (useful to debug issues with publish/import).
- `ARCOR2_REST_DEBUG=1` - may be used to debug problems related to communication with the Project service.
- `ARCOR2_REST_API_DEBUG=1` - turns on Flask debugging (logs each endpoint call).
- `ARCOR2_PROJECT_PATH=""` - can be set to an arbitrary value, not actually used.
