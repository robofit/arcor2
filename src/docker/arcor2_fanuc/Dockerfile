FROM python:3.9.14-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends curl=7.74.0-1.3+deb11u3 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

COPY src.python.arcor2_fanuc.scripts/fanuc.pex /root/fanuc.pex
COPY src/docker/arcor2_fanuc/start.sh /root/start.sh

EXPOSE 5027
ENV PYTHONOPTIMIZE=1