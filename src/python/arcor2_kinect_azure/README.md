# Kinect Azure Service

## Usage Instructions

- By default, the service runs on port 5016.
  - This can be changed by setting `ARCOR2_KINECT_AZURE_URL`.
- You may need to run following commands when using the real sensor to set permissions:

```bash
sudo wget https://raw.githubusercontent.com/microsoft/Azure-Kinect-Sensor-SDK/develop/scripts/99-k4a.rules -P /etc/udev/rules.d/
sudo udevadm control --reload-rules && udevadm trigger
```

## Environment variables

- `ARCOR2_KINECT_AZURE_URL=http://localhost:5016` - by default, the service listens on port 5016.
- `ARCOR2_KINECT_AZURE_MOCK=1` - the service will start in a mock (simulator) mode.
- `ARCOR2_REST_API_DEBUG=1` - turns on Flask debugging (logs each endpoint call).