FROM python:3.12.12-bookworm as deps
COPY src.python.arcor2_calibration.scripts/calibration.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.12.12-bookworm as srcs
COPY src.python.arcor2_calibration.scripts/calibration.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.12.12-bookworm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# libgomp1 and libusb-1.0-0 are because of Open3D
# curl is for healthcheck
RUN set -euo pipefail \
        && apt-get update \
        && apt-get install -y -q --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libgomp1 \
        libusb-1.0-0 \
        curl \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

COPY src/docker/arcor2_calibration/start.sh /root/start.sh

ENTRYPOINT ["/root/start.sh"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5014/healthz/ready || exit 1
