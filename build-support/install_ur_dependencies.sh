#!/usr/bin/env bash

# Keep ROS packages pinned so CI and the arcor2_ur image exercise the same UR stack over time.
apt-get install -y -q --no-install-recommends \
	ros-jazzy-ros-base=0.11.0-1noble.20261006.035407 \
	ros-jazzy-ur=3.9.0-1noble.20261006.044441 \
	ros-jazzy-moveit-py=2.12.4-1noble.20260915.204252
