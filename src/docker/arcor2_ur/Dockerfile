FROM ubuntu:24.04 AS deps
COPY src.python.arcor2_ur.scripts/ur.pex /binary.pex
RUN apt-get update && apt-get install -y -q --no-install-recommends \
    python3=3.12.3-0ubuntu2
RUN PEX_TOOLS=1 python3 /binary.pex venv --scope=deps --compile /bin/app

FROM ubuntu:24.04 AS srcs
COPY src.python.arcor2_ur.scripts/ur.pex /binary.pex
RUN apt-get update && apt-get install -y -q --no-install-recommends \
    python3=3.12.3-0ubuntu2
RUN PEX_TOOLS=1 python3 /binary.pex venv --scope=srcs --compile /bin/app

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y -q --no-install-recommends \
    python3=3.12.3-0ubuntu2 \
    curl=8.5.0-2ubuntu10.3 \
    gnupg2=2.4.4-2ubuntu17 \
    lsb-release=12.0-2 \
    locales=2.39-0ubuntu8 \
    software-properties-common=0.99.48 \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN add-apt-repository universe

ENV LANG=en_US.UTF-8
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

# hadolint ignore=SC2086
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo \"${UBUNTU_CODENAME}\") main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

COPY build-support/install_ur_dependencies.sh /root/install_ur_dependencies.sh

# libgl1-mesa-glx ??
RUN apt-get update \
        && /root/install_ur_dependencies.sh \
        && apt-get install -y -q --no-install-recommends \
        libglib2.0-0=2.80.0-6ubuntu3.1 \
        libgomp1=14-20240412-0ubuntu1 libusb-1.0-0=2:1.0.27-1 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

RUN echo "source /opt/ros/jazzy/setup.bash" >> /etc/bash.bashrc

COPY src/docker/arcor2_ur/start.sh /root/start.sh
RUN chmod +x /root/start.sh
ENTRYPOINT ["/root/start.sh"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 5012

HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5012/healthz/ready || exit 1
