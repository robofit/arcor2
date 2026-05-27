#!/bin/bash

set -e

# shellcheck source=/dev/null
source /opt/ros/jazzy/setup.bash

: "${ARCOR2_UR_TYPE:=ur5e}"
: "${ARCOR2_UR_START_ROBOT_PUBLISHER:=true}"

# simulator needs some time to get running...
if [[ -n "$ARCOR2_UR_STARTUP_SLEEP" && "$ARCOR2_UR_STARTUP_SLEEP" =~ ^[0-9]+$ ]]; then
	echo "Waiting for $ARCOR2_UR_STARTUP_SLEEP seconds..."
	sleep "$ARCOR2_UR_STARTUP_SLEEP"
fi

cp --update=none "$(ros2 pkg prefix --share ur_description)/config/$ARCOR2_UR_TYPE/default_kinematics.yaml" /root/robot_calibration.yaml

ros2 launch ur_robot_driver ur_control.launch.py ur_type:="$ARCOR2_UR_TYPE" robot_ip:="$ARCOR2_UR_ROBOT_IP" launch_rviz:=false kinematics_params_file:="/root/robot_calibration.yaml" &

if [[ "$ARCOR2_UR_START_ROBOT_PUBLISHER" == "true" ]]; then
	echo "Starting ARCOR2 UR robot publisher for suction TCP static transforms..."
	PEX_EXTRA_SYS_PATH=/opt/ros/jazzy/lib/python3.12/site-packages PYTHONOPTIMIZE=1 python3 /bin/robot_publisher.pex &
fi

PEX_EXTRA_SYS_PATH=/opt/ros/jazzy/lib/python3.12/site-packages PYTHONOPTIMIZE=1 /bin/app/pex
