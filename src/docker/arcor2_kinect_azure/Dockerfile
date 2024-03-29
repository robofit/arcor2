FROM python:3.10.10-slim-bullseye as deps
COPY src.python.arcor2_kinect_azure.scripts/kinect_azure.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.10.10-slim-bullseye as srcs
COPY src.python.arcor2_kinect_azure.scripts/kinect_azure.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.10.10-slim-bullseye

COPY build-support/install_kinect_prerequisites.sh /root/install_kinect_prerequisites.sh

# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=20.3.5-1 libglib2.0-0=2.66.8-1+deb11u1 gnupg2=2.2.27-2+deb11u2 curl=7.74.0-1.3+deb11u11 \
        && /root/install_kinect_prerequisites.sh \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 5016
HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5016/healthz/ready || exit 1
