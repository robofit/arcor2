FROM python:3.9.14-slim-bullseye
ENTRYPOINT ["/root/start.sh"]

RUN mkdir -p /root/tokens \
	&& mkdir -p /root/project

COPY src.python.arcor2_execution_rest_proxy.scripts/execution_rest_proxy.pex /root/execution_rest_proxy.pex
COPY src/docker/arcor2_execution_proxy/start.sh /root/start.sh

EXPOSE 5009
ENV PYTHONOPTIMIZE=1