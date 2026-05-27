#!/usr/bin/env bash
set -euxo pipefail

apt-get update

# debug check
apt-cache search ros-jazzy | head || true

# Keep ROS packages pinned so CI and the arcor2_ur image exercise the same UR stack over time.
apt-get install -y -q --no-install-recommends \
	ros-jazzy-ros-base=0.11.0-1noble.20260412.071950 \
	ros-jazzy-ur=3.7.0-1noble.20260412.082316 \
	ros-jazzy-moveit-py=2.12.4-1noble.20260412.073026
