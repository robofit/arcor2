FROM python:3.12.12-bookworm as deps
COPY src.python.arcor2_arserver.scripts/arserver.pex /binary.pex
RUN PEX_TOOLS=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.12.12-bookworm as srcs
COPY src.python.arcor2_arserver.scripts/arserver.pex /binary.pex
RUN PEX_TOOLS=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.12.12-bookworm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -euo pipefail \
        && apt-get update \
        && apt-get install -y -q --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir uploadserver==5.2.1

COPY src/docker/arcor2_arserver/start.sh /root/start.sh

ENTRYPOINT ["/root/start.sh"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

RUN mkdir -p /root/data
