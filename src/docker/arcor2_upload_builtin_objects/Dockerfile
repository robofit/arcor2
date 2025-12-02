FROM python:3.12.7-bookworm as deps
COPY src.python.arcor2.scripts/upload_builtin_objects.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=deps --compile /bin/app

FROM python:3.12.7-bookworm as srcs
COPY src.python.arcor2.scripts/upload_builtin_objects.pex /binary.pex
RUN PEX_TOOLS=1 PYTHONOPTIMIZE=1 /usr/local/bin/python /binary.pex venv --scope=srcs --compile /bin/app

FROM python:3.12.7-bookworm

ENTRYPOINT ["/bin/app/pex"]
COPY --from=deps /bin/app /bin/app
COPY --from=srcs /bin/app /bin/app