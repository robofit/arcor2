#!/usr/bin/env bash

set -e

# on Ubuntu 18.04 it is necessary to install Python 3.8 first
# see https://vsupalov.com/developing-with-python3-8-on-ubuntu-18-04/
# also don't forget to run sudo apt install python3.8-venv python3.8-dev (otherwise ensurepip module won't be available)

PYTHON_BIN=python3.8
VIRTUALENV=build-support/.venv
PIP="${VIRTUALENV}/bin/pip"

"${PYTHON_BIN}" -m venv "${VIRTUALENV}"
"${PIP}" install pip --upgrade
"${PIP}" install -r <(./pants dependencies --type=3rdparty ::)