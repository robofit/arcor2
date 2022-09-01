FROM python:3.9-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

COPY src.python.arcor2_mocks.scripts/mock_project.pex /root/mock_project.pex
COPY src.python.arcor2_mocks.scripts/mock_scene.pex /root/mock_scene.pex

# libgomp1 and libusb-1.0-0 are because of Open3D
# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1 libgomp1=10.2.1-6 libusb-1.0-0=2:1.0.24-3 curl=7.74.0-1.3+deb11u2 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

COPY src/docker/arcor2_mocks/start.sh /root/start.sh