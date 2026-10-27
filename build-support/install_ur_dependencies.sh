#!/usr/bin/env bash

# Keep ROS packages pinned so CI and the arcor2_ur image exercise the same UR stack over time.
# packages.ros.org keeps only the newest build of each package, so the pins are installed from a dated snapshot
# of it instead. To upgrade the UR stack, pick a newer snapshot from http://snapshots.ros.org/jazzy/ and update
# the pins to the versions listed in its dists/noble/main/binary-amd64/Packages.gz.
# Requires curl and gpg.

set -euo pipefail

ROS_SNAPSHOT="2026-10-05"
# "ROS Snapshot builder" key; the keyserver serves its current expiry date, so an extended key is picked up.
ROS_SNAPSHOT_KEY="4B63CF8FDE49746E98FA01DDAD19BAB3CBF125EA"
KEYRING="/usr/share/keyrings/ros-snapshots-archive-keyring.gpg"

curl -sSfL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x${ROS_SNAPSHOT_KEY}" | gpg --batch --yes --dearmor -o "${KEYRING}"

if [ "$(gpg --batch --show-keys --with-colons "${KEYRING}" | awk -F: '/^fpr/ {print $10; exit}')" != "${ROS_SNAPSHOT_KEY}" ]; then
	echo "Unexpected key in ${KEYRING}." >&2
	exit 1
fi

# shellcheck source=/dev/null
CODENAME="$(. /etc/os-release && echo "${UBUNTU_CODENAME}")"
echo "deb [arch=$(dpkg --print-architecture) signed-by=${KEYRING}] http://snapshots.ros.org/jazzy/${ROS_SNAPSHOT}/ubuntu ${CODENAME} main" >/etc/apt/sources.list.d/ros2-snapshots.list

apt-get update
apt-get install -y -q --no-install-recommends \
	ros-jazzy-ros-base=0.11.0-1noble.20261006.035407 \
	ros-jazzy-ur=3.9.0-1noble.20261006.044441 \
	ros-jazzy-moveit-py=2.12.4-1noble.20260915.204252
