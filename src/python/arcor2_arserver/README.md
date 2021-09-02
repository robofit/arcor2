# arcor2_arserver

## Environment variables

- `ARCOR2_ARSERVER_PORT=6789` - by default, the service will listen on port 6789.

### Caching

- `ARCOR2_ARSERVER_CACHE_TIMEOUT=1.0` - by default, ARServer checks for changes in scenes, projects or ObjectTypes max. once per second.
- `ARCOR2_ARSERVER_CACHE_SCENES=32` - by default, ARServer keeps 32 last used scenes in its cache.
- `ARCOR2_ARSERVER_CACHE_PROJECTS=64` - by default, ARServer keeps 64 last used projects in its cache.
- `ARCOR2_ARSERVER_CACHE_OBJECT_TYPES=32` - by default, ARServer keeps 64 last used ObjectTypes in its cache.

### Debugging

- `ARCOR2_MAX_RPC_DURATION=0.1` - by default, a warning is emitted when any RPC call takes longer than 0.1 second.
- `ARCOR2_ARSERVER_DEBUG=1` - switches logger to the `DEBUG` level. 
- `ARCOR2_ARSERVER_ASYNCIO_DEBUG=1` - turns on `asyncio` debug output (helpful to debug problems related to concurrency). 
- `ARCOR2_REST_DEBUG=1` - may be used to debug problems related to communication with the Project, Scene Build and Calibration services. 