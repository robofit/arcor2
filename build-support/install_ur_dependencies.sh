#!/usr/bin/env bash
set -euxo pipefail

apt-get update

# debug - ukáž dostupnosť a verzie presne tých balíkov čo inštaluješ
apt-cache policy ros-jazzy-ros-base ros-jazzy-ur ros-jazzy-moveit-py || true
apt-cache madison ros-jazzy-ros-base ros-jazzy-ur ros-jazzy-moveit-py || true

apt-get install -y -q --no-install-recommends \
  ros-jazzy-ros-base=0.11.0-1noble.20251108.003726 \
  ros-jazzy-ur=3.6.0-1noble.20251114.095610 \
  ros-jazzy-moveit-py=2.12.3-1noble.20251108.011222