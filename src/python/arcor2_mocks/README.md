# arcor2_mocks


## Environment variables

- `ARCOR2_PROJECT_SERVICE_MOCK_PORT=5012` - by default, the Project mock listens on port 5012.
- `ARCOR2_SCENE_SERVICE_MOCK_PORT=5013` - by default, the Scene mock listens on port 5013.
- `ARCOR2_REST_API_DEBUG=1` - turns on Flask debugging (logs each endpoint call).

### Scene Service Mock

- `ARCOR2_SCENE_DEBUG=1` - turns on debug logging.
- `ARCOR2_SCENE_INFLATION=0.01` - controls how much in meters are collision models inflated (for simple collision checking).
- `ARCOR2_MOCK_SCENE_DELAY_MEAN=0` and `ARCOR2_MOCK_SCENE_DELAY_SIGMA=0` can be used to simulate long-lasting startup of the scene (with some randomness). May be useful for debugging.