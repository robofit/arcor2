FROM python:3.11.12-bookworm as deps
COPY src.python.arcor2_arserver.scripts/arserver.pex /binary.pex
RUN PEX_TOOLS=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.11.12-bookworm as srcs
COPY src.python.arcor2_arserver.scripts/arserver.pex /binary.pex
RUN PEX_TOOLS=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.11.12-bookworm

RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=22.3.6-1+deb12u1 libglib2.0-0=2.74.6-2+deb12u5 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir uploadserver==5.2.1

COPY src/docker/arcor2_arserver/start.sh /root/start.sh

ENTRYPOINT ["/root/start.sh"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

RUN mkdir -p /root/data
