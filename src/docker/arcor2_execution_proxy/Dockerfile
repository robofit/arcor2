FROM python:3.12.7-bookworm as deps
COPY src.python.arcor2_execution_rest_proxy.scripts/execution_rest_proxy.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.12.7-bookworm as srcs
COPY src.python.arcor2_execution_rest_proxy.scripts/execution_rest_proxy.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.12.7-bookworm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN mkdir -p /root/tokens \
	&& mkdir -p /root/project

# curl is for healthcheck
RUN set -euo pipefail \
        && apt-get update \
        && curl_ver="$(apt-cache policy curl | awk '/Candidate:/ {print $2}')" \
        && apt-get install -y -q --no-install-recommends \
        "curl=${curl_ver}" \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

EXPOSE 5009
HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5009/healthz/ready || exit 1
