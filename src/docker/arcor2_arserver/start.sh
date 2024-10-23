#!/bin/bash

mkdir -p "${ARCOR2_AREDITOR_LOGS_FOLDER:-/root/logs}"
python3 -m uploadserver --directory "${ARCOR2_AREDITOR_LOGS_FOLDER:-/root/logs}" 6799 &
PYTHONOPTIMIZE=1 /bin/app/pex
