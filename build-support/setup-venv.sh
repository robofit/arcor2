#!/usr/bin/env bash

set -e

# on Ubuntu 18.04 it is necessary to install Python 3.9 first
# see https://vsupalov.com/developing-with-python3-8-on-ubuntu-18-04/
# also don't forget to run sudo apt install python3.9-venv python3.9-dev (otherwise ensurepip module won't be available)

PYTHON_BIN=python3.10
VIRTUALENV=build-support/.venv
PIP="${VIRTUALENV}/bin/pip"
REQUIREMENTS_FILE=3rdparty/requirements.txt
CONSTRAINTS_FILE=3rdparty/constraints.txt


"${PYTHON_BIN}" -m venv "${VIRTUALENV}"
"${PIP}" install pip --upgrade
"${PIP}" install -r "${REQUIREMENTS_FILE}" \
                 -c "${CONSTRAINTS_FILE}"
