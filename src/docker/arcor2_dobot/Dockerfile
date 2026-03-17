FROM python:3.14.3-bookworm as deps
COPY src.python.arcor2_dobot.scripts/dobot.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.14.3-bookworm as srcs
COPY src.python.arcor2_dobot.scripts/dobot.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.14.3-bookworm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

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

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 5018

HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5018/healthz/ready || exit 1
