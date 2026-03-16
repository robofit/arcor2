#!/usr/bin/env bash

# Keep ROS packages pinned so CI and the arcor2_ur image exercise the same UR stack over time.
apt-get install -y -q --no-install-recommends \
	ros-jazzy-ros-base=0.11.0-1noble.20260126.203129 \
	ros-jazzy-ur=3.7.0-1noble.20260126.222208 \
	ros-jazzy-moveit-py=2.12.4-1noble.20260126.215035
