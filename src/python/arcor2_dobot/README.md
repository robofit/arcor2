# arcor2_dobot

## Environment variables

- `ARCOR2_DOBOT_URL=http://0.0.0.0:5018` - by default, the service listens on port 5018.
- `ARCOR2_DOBOT_MODEL=magician` - can be set to `magician` or `m1`.
- `ARCOR2_DOBOT_MOCK=1` - the service will start in a mock (simulator) mode.
  - Please note that the mock mode is fully functional only for `magician`. The `m1` does not have IK/FK implemented yet.
 `ARCOR2_DOBOT_DEBUG=1` - turns on debug logging.