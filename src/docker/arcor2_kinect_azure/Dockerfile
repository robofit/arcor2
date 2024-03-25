FROM python:3.11.8-bookworm as deps
COPY src.python.arcor2_kinect_azure.scripts/kinect_azure.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.11.8-bookworm as srcs
COPY src.python.arcor2_kinect_azure.scripts/kinect_azure.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.11.8-bookworm

COPY build-support/install_kinect_prerequisites.sh /root/install_kinect_prerequisites.sh

# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends libgl1-mesa-glx=22.3.6-1+deb12u1 libglib2.0-0=2.74.6-2 gnupg2=2.2.40-1.1 curl=7.88.1-10+deb12u5 \
        && /root/install_kinect_prerequisites.sh \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 5016
HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5016/healthz/ready || exit 1
