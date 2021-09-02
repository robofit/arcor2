# ARCOR2 Calibration service

### Example configuration

```yaml
id: Arbitrary text
marker_size: 0.1
markers:
  10:
    pose:
      position:
        x: 0
        y: 0
        z: 0
      orientation:
        x: 0
        y: 0
        z: 0
        w: 1
```

## Environment variables

- `ARCOR2_CALIBRATION_URL=http://0.0.0.0:5014` - by default, the service listens on port 5014.
- `ARCOR2_CALIBRATION_DEBUG=1` - switches logger to the `DEBUG` level.
- `ARCOR2_CALIBRATION_MOCK=1` - the service will start in a mock (simulator) mode.
- `ARCOR2_REST_API_DEBUG=1` - turns on Flask debugging (logs each endpoint call).