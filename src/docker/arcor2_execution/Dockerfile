FROM python:3.10.9-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

RUN mkdir -p /root/project

COPY src.python.arcor2_execution.scripts/execution.pex /root/execution.pex

RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

COPY src/docker/arcor2_execution/start.sh /root/start.sh

EXPOSE 6790
ENV PYTHONOPTIMIZE=1