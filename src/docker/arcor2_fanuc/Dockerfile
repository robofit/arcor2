FROM python:3.9-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

COPY src.python.arcor2_fanuc.scripts/fanuc.pex /root/fanuc.pex
COPY src/docker/arcor2_fanuc/start.sh /root/start.sh

EXPOSE 5027