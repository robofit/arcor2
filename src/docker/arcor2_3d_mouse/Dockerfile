

FROM python:3.11.9-bookworm as deps
COPY src.python.arcor2_3d_mouse.scripts/mouse_launcher.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.11.9-bookworm as srcs
COPY src.python.arcor2_3d_mouse.scripts/mouse_launcher.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.11.9-bookworm

# curl is for healthcheck
RUN apt-get update \
	&& apt-get -f satisfy ffmpeg -y \
        && apt-get install -y -q --no-install-recommends sudo=1.9.13p3-1+deb12u1 libhidapi-dev=0.13.1-1 libpulse0=16.1+dfsg1-2+b1 libasound2=1.2.8-1+b1 libasound2-plugins=1.2.7.1-1 curl=7.88.1-10+deb12u5 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ARG UID=1000

ARG TINI=v0.18.0

ENV PULSE_SERVER=unix:/run/user/$UID/pulse/native

ENV G_UID=1000

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app


