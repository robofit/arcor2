FROM python:3.12.7-bookworm as deps
COPY src.python.arcor2_execution.scripts/execution.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.12.7-bookworm as srcs
COPY src.python.arcor2_execution.scripts/execution.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.12.7-bookworm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -euo pipefail \
        && apt-get update \
        && apt-get install -y -q --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 6790
