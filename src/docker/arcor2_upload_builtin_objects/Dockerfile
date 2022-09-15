FROM python:3.9.14-slim-bullseye

COPY src.python.arcor2.scripts/upload_builtin_objects.pex /root/upload_objects.pex

ENV PYTHONOPTIMIZE=1
CMD ["python", "/root/upload_objects.pex"]