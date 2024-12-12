# arcor2_ur

The service communicates over ROS 2 and MoveItPy with Universal Robots and provides simple REST API to control the robot and allow integration into ARCOR2.

It is tested with Ubuntu 24.04, ROS 2 Jazzy and the UR5e robot - however, it should be possible to use it with any robot supported by the [ROS 2 driver](https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver/tree/main). It expects that the `ur_control.launch.py` is already running (which is handled in the [docker image](https://github.com/robofit/arcor2/blob/master/src/docker/arcor2_ur/start.sh)).

This service also offers API for managing collision objects. The API is compatible with `arcor2_scene`, meaning that the standard client `arcor2.clients.scene_service` can be used, and it is also fully compatible with ARServer. Typically, in ARCOR2 architecture, this would be done by a separate service. This solution was chosen for simplicity. In the future, there might be something like `arcor2_scene_ros2`, which would enable managing collision objects for multiple robots (which could be just a proxy for forwarding collision object requests to individual ROS-based robots, if they will use separate ROS domains). 

## Setup
 
- To prepare the robot, please install external control URCap using following [instructions](https://docs.ros.org/en/ros2_packages/rolling/api/ur_robot_driver/installation/install_urcap_e_series.html). When configuring it, enter server's hostname into "remote host IP". Name the program `prog.urp` - it will be automatically started by the service.
- [RS485 URCap](https://github.com/UniversalRobots/Universal_Robots_ToolComm_Forwarder_URCap) is required for communication with OnRobot VGC10 suction. In "Installation/Tool IO", please set "Controlled by" to "User"
and "Tool Output Voltage" to "24".
- A real-time system is highly recommended for running the service. The easiest way is through the [Ubuntu Pro](https://documentation.ubuntu.com/pro/pro-client/enable_realtime_kernel/).
- Before starting the service, put robot into "Remote Control" mode.

## Environment variables

- `ARCOR2_UR_URL=http://0.0.0.0:5012` - by default, the service listens on port 5012 (Swagger UI can be found at e.g. [http://localhost:5012/swagger](http://localhost:5012/swagger)).
- `ARCOR2_UR_DEBUG=1` - turns on debug logging.
- `ARCOR2_UR_BASE_LINK=base_link` - sets base_link of the robot (the frame in which EEF coordinates are expressed).
- `ARCOR2_UR_TOOL_LINK=tool0` - the frame representing EEF pose.
- `ARCOR2_UR_TYPE=ur5e` - sets type of the robot.
- `PLANNING_GROUP_NAME=ur_manipulator` - planning group which is going to be controlled by this service.
- `ARCOR2_UR_INTERACT_WITH_DASHBOARD=true` - can be used to disable interaction with dashboard (controls brakes, starts `prog.urp`, etc.). 
- `ARCOR2_UR_ROBOT_IP=""` - used for Modbus RTU over TCP (tool communication). When empty, the service "simulates" the tool by just accepting all calls and returning default values.
- `ARCOR2_UR_VGC10_PORT=54321` - port used by ToolComm Forwarder URCap. 

## Known Problems

- The service crashes on `PUT /state/stop` (but is automatically restarted when using Docker compose).
- Call to `PUT /state/start` should initialize the robot, but it does not work at the moment. Please start robot manually before calling it. If the call fails anyway, please try again. Usually, the next time it works properly.