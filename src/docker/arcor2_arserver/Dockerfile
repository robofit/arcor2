FROM python:3.10.9-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

RUN mkdir -p /root/data

COPY src.python.arcor2_arserver.scripts/arserver.pex /root/arserver.pex

RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir uploadserver==2.0.1

COPY src/docker/arcor2_arserver/start.sh /root/start.sh

ENV PYTHONOPTIMIZE=1