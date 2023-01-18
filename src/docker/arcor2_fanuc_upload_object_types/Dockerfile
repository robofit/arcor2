FROM python:3.10.9-slim-bullseye

COPY src.python.arcor2_fanuc.scripts/upload_objects.pex /root/upload_objects.pex

ENV PYTHONOPTIMIZE=1
CMD ["python", "/root/upload_objects.pex"]