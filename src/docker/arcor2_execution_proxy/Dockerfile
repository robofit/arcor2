FROM python:3.10.10-slim-bullseye as deps
COPY src.python.arcor2_execution_rest_proxy.scripts/execution_rest_proxy.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.10.10-slim-bullseye as srcs
COPY src.python.arcor2_execution_rest_proxy.scripts/execution_rest_proxy.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python3.10 /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.10.10-slim-bullseye

RUN mkdir -p /root/tokens \
	&& mkdir -p /root/project

# curl is for healthcheck
RUN apt-get update \
        && apt-get install -y -q --no-install-recommends curl=7.74.0-1.3+deb11u11 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 5009
HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5009/healthz/ready || exit 1
