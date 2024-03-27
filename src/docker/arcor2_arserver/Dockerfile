FROM python:3.10.10-slim-bullseye as deps
COPY src.python.arcor2_arserver.scripts/arserver.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.10.10-slim-bullseye as srcs
COPY src.python.arcor2_arserver.scripts/arserver.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.10.10-slim-bullseye

RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1+deb11u1 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir uploadserver==2.0.1

COPY src/docker/arcor2_arserver/start.sh /root/start.sh

ENTRYPOINT ["/root/start.sh"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

RUN mkdir -p /root/data