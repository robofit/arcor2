FROM python:3.9.14-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1 libgomp1=10.2.1-6 libusb-1.0-0=2:1.0.24-3 curl=7.74.0-1.3+deb11u3 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

COPY src.python.arcor2_dobot.scripts/dobot.pex /root/dobot.pex
COPY src/docker/arcor2_dobot/start.sh /root/start.sh
ENV PYTHONOPTIMIZE=1