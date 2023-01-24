# Kinect Azure Service

## Usage Instructions

- By default, the service runs on port 5016.
    - This can be changed by setting `ARCOR2_KINECT_AZURE_URL`.
- Kinect SDK has to be installed beforehand (`sudo ./build-support/install_kinect_prerequisites.sh`).
- You may need to run following commands when using the real sensor to set permissions:

```bash
sudo wget https://raw.githubusercontent.com/microsoft/Azure-Kinect-Sensor-SDK/develop/scripts/99-k4a.rules -P /etc/udev/rules.d/
sudo udevadm control --reload-rules && udevadm trigger
```

- The real kinect needs display. Insert any dummy HDMI plug to graphics card or plug in real monitor.
- When all of the above is done, execute `./pants run src/python/arcor2_kinect_azure/scripts/kinect_azure.py` and the app should run without any problem

#### Note that the app cannot run in docker when using real kinect device. Follow steps above to run in production

## Environment variables

- `ARCOR2_KINECT_AZURE_URL=http://0.0.0.0:5016` - by default, the service listens on port 5016.
- `ARCOR2_KINECT_AZURE_MOCK=1` - the service will start in a mock (simulator) mode.
- `ARCOR2_REST_API_DEBUG=1` - turns on Flask debugging (logs each endpoint call).
- `ARCOR2_KINECT_AZURE_DEBUG=1` - turns on additional debugging