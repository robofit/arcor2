#!/usr/bin/env bash

set -e

# on Ubuntu 18.04 it is necessary to install Python 3.8 first
# see https://vsupalov.com/developing-with-python3-8-on-ubuntu-18-04/
# also don't forget to run sudo apt install python3.8-venv python3.8-dev (otherwise ensurepip module won't be available)

PYTHON_BIN=python3.8
VIRTUALENV=build-support/.constr_venv
PIP="${VIRTUALENV}/bin/pip"
REQUIREMENTS_FILE=3rdparty/requirements.txt
CONSTRAINTS_FILE=3rdparty/constraints.txt

if [ -d "${VIRTUALENV}" ]; then rm -Rf "${VIRTUALENV}"; fi  # not sure if this is necessary

"${PYTHON_BIN}" -m venv "${VIRTUALENV}"
"${PIP}" install pip --upgrade
"${PIP}" install -r <(./pants dependencies --type=3rdparty ::)

# Install all our requirements.txt, and also any 3rdparty
# dependencies specified outside requirements.txt, e.g. via a
# handwritten python_requirement_library target.
"${PIP}" install \
  -r "${REQUIREMENTS_FILE}" \
  -r <(./pants dependencies --type=3rdparty ::)
echo "# Generated by build-support/generate_constraints.sh on $(date)" > "${CONSTRAINTS_FILE}"
"${PIP}" freeze --all >> "${CONSTRAINTS_FILE}"

rm -r "${VIRTUALENV}"