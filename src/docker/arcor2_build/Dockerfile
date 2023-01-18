FROM python:3.10.8-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

COPY src.python.arcor2_build.scripts/build.pex /root/build.pex

# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1 curl=7.74.0-1.3+deb11u3 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

COPY src/docker/arcor2_build/start.sh /root/start.sh

EXPOSE 5008
ENV PYTHONOPTIMIZE=1

HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5008/healthz/ready || exit 1