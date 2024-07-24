#!/bin/bash

# shellcheck source=/dev/null
source /opt/ros/jazzy/setup.bash

: "${UR_TYPE:=ur5e}"
: "${ROBOT_CONTAINER_NAME:=ur-demo-ursim}"

ROBOT_CONTAINER_IP=$(getent hosts "$ROBOT_CONTAINER_NAME" | awk '{ print $1 }')

sleep 10s # TODO find a way how to detect that the robot is up and running (test if some port is opened?)

ros2 launch ur_robot_driver ur_control.launch.py ur_type:="$UR_TYPE" robot_ip:="$ROBOT_CONTAINER_IP" launch_rviz:=false &

PEX_EXTRA_SYS_PATH=/opt/ros/jazzy/lib/python3.12/site-packages /bin/app/pex
