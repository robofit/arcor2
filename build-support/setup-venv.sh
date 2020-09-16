#!/usr/bin/env bash

set -e

PYTHON_BIN=python3  # TODO use python3.8
VIRTUALENV=build-support/.venv
PIP="${VIRTUALENV}/bin/pip"

"${PYTHON_BIN}" -m venv "${VIRTUALENV}"
"${PIP}" install pip --upgrade
"${PIP}" install -r <(./pants dependencies --type=3rdparty ::)