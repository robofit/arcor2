# arcor2_ur

The service communicates over ROS 2 and MoveItPy with Universal Robots and provides simple REST API to control the robot and allow integration into ARCOR2.

The service is tested with Ubuntu 24.04, ROS 2 Jazzy and the UR5e robot - however, it should be possible to use it with any robot supported by the [ROS 2 driver](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/tree/main). It expects that the `ur_control.launch.py` is already running (which is handled in the [docker image](https://github.com/robofit/arcor2/blob/master/src/docker/arcor2_ur/start.sh)).

## Setup
 
- To prepare the robot, please install external control URCap using following [instructions](https://docs.ros.org/en/ros2_packages/rolling/api/ur_robot_driver/installation/install_urcap_e_series.html). When configuring it, enter server's hostname into "remote host IP". Name the program `prog.urp` - it will be automatically started by the service.
- A real-time system is highly recommended for running the service. The easiest way is through the [Ubuntu Pro](https://documentation.ubuntu.com/pro/pro-client/enable_realtime_kernel/). 

## Environment variables

- `ARCOR2_UR_URL=http://0.0.0.0:5012` - by default, the service listens on port 5012 (Swagger UI can be found at e.g. [http://localhost:5012/swagger](http://localhost:5012/swagger)).
- `ARCOR2_UR_DEBUG=1` - turns on debug logging.
- `ARCOR2_UR_BASE_LINK=base_link` - sets base_link of the robot (the frame in which EEF coordinates are expressed).
- `ARCOR2_UR_TOOL_LINK=tool0` - the frame representing EEF pose.
- `ARCOR2_UR_TYPE=ur5e` - sets type of the robot.
- `PLANNING_GROUP_NAME=ur_manipulator` - planning group which is going to be controlled by this service.
- `ARCOR2_UR_INTERACT_WITH_DASHBOARD=true` - can be used to disable interaction with dashboard (controls brakes, starts `prog.urp`, etc.). 

## Known Problems

- The service crashes on `PUT /state/stop`.
- Sometimes, calling `PUT /state/start` (which initializes robot and MoveIt) fails. Usually, the next time it works properly.
