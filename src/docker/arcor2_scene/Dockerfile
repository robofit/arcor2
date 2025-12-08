FROM python:3.12.7-bookworm as deps
COPY src.python.arcor2_scene.scripts/scene.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.12.7-bookworm as srcs
COPY src.python.arcor2_scene.scripts/scene.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.12.7-bookworm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# libgomp1 and libusb-1.0-0 are because of Open3D
# curl is for healthcheck
RUN set -euo pipefail \
        && apt-get update \
        && gl_ver="$(apt-cache policy libgl1-mesa-glx | awk '/Candidate:/ {print $2}')" \
        && glib_ver="$(apt-cache policy libglib2.0-0 | awk '/Candidate:/ {print $2}')" \
        && gomp_ver="$(apt-cache policy libgomp1 | awk '/Candidate:/ {print $2}')" \
        && libusb_ver="$(apt-cache policy libusb-1.0-0 | awk '/Candidate:/ {print $2}')" \
        && curl_ver="$(apt-cache policy curl | awk '/Candidate:/ {print $2}')" \
        && apt-get install -y -q --no-install-recommends \
        "libgl1-mesa-glx=${gl_ver}" \
        "libglib2.0-0=${glib_ver}" \
        "libgomp1=${gomp_ver}" \
        "libusb-1.0-0=${libusb_ver}" \
        "curl=${curl_ver}" \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app

HEALTHCHECK --interval=5s --start-period=60s CMD curl -f http://localhost:5013/healthz/ready || exit 1
