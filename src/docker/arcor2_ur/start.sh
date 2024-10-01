#!/bin/bash

set -e

# shellcheck source=/dev/null
source /opt/ros/jazzy/setup.bash

: "${UR_TYPE:=ur5e}"

# simulator needs some time to get running...
if [[ -n "$SLEEP" && "$SLEEP" =~ ^[0-9]+$ ]]; then
	echo "Waiting for $SLEEP seconds..."
	sleep "$SLEEP"
fi

cp --update=none "$(ros2 pkg prefix --share ur_description)/config/$UR_TYPE/default_kinematics.yaml" /root/robot_calibration.yaml

ros2 launch ur_robot_driver ur_control.launch.py ur_type:="$UR_TYPE" robot_ip:="$ROBOT_IP" launch_rviz:=false kinematics_params_file:="/root/robot_calibration.yaml" &

PEX_EXTRA_SYS_PATH=/opt/ros/jazzy/lib/python3.12/site-packages PYTHONOPTIMIZE=1 /bin/app/pex
