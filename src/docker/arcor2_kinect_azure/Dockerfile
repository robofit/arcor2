FROM python:3.10.9-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

COPY src.python.arcor2_kinect_azure.scripts/kinect_azure.pex /root/kinect_azure.pex
COPY build-support/install_kinect_prerequisites.sh /root/install_kinect_prerequisites.sh

# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1 gnupg2=2.2.27-2+deb11u2 curl=7.74.0-1.3+deb11u3 \
        && /root/install_kinect_prerequisites.sh \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

COPY src/docker/arcor2_kinect_azure/start.sh /root/start.sh
ENV PYTHONOPTIMIZE=1