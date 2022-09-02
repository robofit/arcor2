# arcor2_scene

ARCOR2 Scene service has similar functionality to Kinali's Scene service (in version 0.8.0), but not all endpoints are implemented, and on the other hand, there are some additional, specific ones.

## Environment variables

- `ARCOR2_SCENE_SERVICE_PORT=5013` - by default, the Scene mock listens on port 5013.
- `ARCOR2_REST_API_DEBUG=1` - turns on Flask debugging (logs each endpoint call).

- `ARCOR2_SCENE_DEBUG=1` - turns on debug logging.
- `ARCOR2_SCENE_INFLATION=0.01` - controls how much in meters are collision models inflated (for simple collision checking).
- `ARCOR2_SCENE_DELAY_MEAN=0` and `ARCOR2_SCENE_DELAY_SIGMA=0` can be used to simulate long-lasting startup of the scene (with some randomness). May be useful for debugging.