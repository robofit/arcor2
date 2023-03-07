

FROM python:3.10.10-slim-bullseye as deps
COPY src.python.arcor2_3d_mouse.scripts/mouse_launcher.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.10.10-slim-bullseye as srcs
COPY src.python.arcor2_3d_mouse.scripts/mouse_launcher.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.10.10-slim-bullseye

# curl is for healthcheck
RUN apt-get update \
	&& apt-get -f satisfy ffmpeg -y \
        && apt-get install -y -q --no-install-recommends sudo=1.9.5p2-3+deb11u1 libhidapi-dev=0.10.1+dfsg-1 libpulse0=14.2-2 libasound2=1.2.4-1.1 libasound2-plugins=1.2.2-2 curl=7.74.0-1.3+deb11u7 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ARG UID=1000

ARG TINI=v0.18.0

ENV PULSE_SERVER=unix:/run/user/$UID/pulse/native

ENV G_UID=1000

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app


