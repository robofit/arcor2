### ARCOR2 YuMi Demo

Based on [galou/yumipy](https://github.com/galou/yumipy/tree/robotware6_06/yumipy), with a stripped-of support for ROS, adapted to Python 3.8, with added type annotations, etc. The URDF model comes from [OrebroUniversity/yumi](https://github.com/OrebroUniversity/yumi/tree/master/yumi_description) repository.

Tested with RobotWare 6.12.02 and SmartGripper 3.56.

### Functionality

### Limitations

### Ideas for further development / improvements:
- Use `POST /rw/rapid/modules/MainModule?task=T_ROB1&action=set-module-text` to update RAPID during initialization.
  - It would be necessary to somehow assign files on the project service (RAPID) to the ObjectType.