FROM ubuntu:noble AS deps
COPY src.python.arcor2_ur.scripts/ur.pex /binary.pex
RUN apt-get update && apt-get install -y -q --no-install-recommends \
    python3
RUN PEX_TOOLS=1 python3 /binary.pex venv --scope=deps --compile /bin/app

FROM ubuntu:noble AS srcs
COPY src.python.arcor2_ur.scripts/ur.pex /binary.pex
RUN apt-get update && apt-get install -y -q --no-install-recommends \
    python3
RUN PEX_TOOLS=1 python3 /binary.pex venv --scope=srcs --compile /bin/app

FROM ubuntu:noble

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y -q --no-install-recommends \
    python3 \
    curl \
    gnupg2 \
    lsb-release \
    locales \
    software-properties-common \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN add-apt-repository universe

ENV LANG=en_US.UTF-8
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# the script also adds the ROS apt repository (a dated snapshot)
COPY build-support/install_ur_dependencies.sh /root/install_ur_dependencies.sh

# libgl1-mesa-glx ??
RUN set -euo pipefail \
        && /root/install_ur_dependencies.sh \
        && apt-get install -y -q --no-install-recommends \
        libglib2.0-0t64 \
        libgomp1 \
        libusb-1.0-0 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

RUN echo "source /opt/ros/jazzy/setup.bash" >> /etc/bash.bashrc

ENV ARCOR2_UR_TYPE=${ARCOR2_UR_TYPE}
ENV ARCOR2_UR_ROBOT_IP=${ARCOR2_UR_ROBOT_IP}
ENV ARCOR2_UR_STARTUP_SLEEP=${ARCOR2_UR_STARTUP_SLEEP}

COPY src/docker/arcor2_ur/start.sh /root/start.sh
RUN chmod +x /root/start.sh
ENTRYPOINT ["/root/start.sh"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 5012

HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5012/healthz/ready || exit 1
