# ARCOR2

**ARCOR** stands for **A**ugmented **R**eality **C**ollaborative **R**obot. It is a system for simplified programming of collaborative robots based on augmented reality developed by [Robo@FIT](https://www.fit.vut.cz/research/group/robo/.en). 

This repository contains the backend solution. It can be easily tested out or deployed using [docker images](https://hub.docker.com/u/arcor2). Unity-based client application for ARCore-supported tablets is available [here](https://github.com/robofit/arcor2_editor).

Initial development was supported by [Test-it-off: Robotic offline product testing](https://www.fit.vut.cz/research/project/1308/) project (Ministry of Industry and Trade of the Czech Republic). 

For more technical and development-related information, please see our [wiki](https://github.com/robofit/arcor2/wiki).

## Videos

To get an idea of what our research is about, take a look at a video that was created in collaboration with ABB:

[![Augmented Reality in Robot Programming: ABB YuMi showcase](http://i3.ytimg.com/vi/1sN1aUmuBjg/hqdefault.jpg)](https://youtu.be/1sN1aUmuBjg)

The video presenting the ARCOR2 system and its development in detail:

[![ARCOR2: Framework for Collaborative End-User Management of Industrial Robotic Workplaces using AR](https://img.youtube.com/vi/RI1uiIEiPK8/hqdefault.jpg)](https://youtu.be/RI1uiIEiPK8)

The following video by [Kinali](https://www.kinali.cz/en/) shows the use case (offline PCB testing), where the system was applied:

[![Test-it-off: robotic system for automatic products inspection](http://i3.ytimg.com/vi/6uktcrJCmc0/hqdefault.jpg)](https://youtu.be/6uktcrJCmc0)

## Usage

Most users will stick to [Docker images](https://hub.docker.com/u/arcor2). The easiest method how to get started, is to run [fit-demo](https://github.com/robofit/arcor2/tree/master/compose-files/fit-demo) compose file, which (by default) does not need any hardware. You can just connect using a tablet with AREditor and play around. Alternatively, all packages are also published on [PyPI](https://pypi.org/user/robo_fit/), which might be helpful for advanced use cases. For information about changes, please see individual changelogs, or the [Releases](https://github.com/robofit/arcor2/releases) page.

## Publications
 
- Kapinus, Michal, et al. "Spatially situated end-user robot programming in augmented reality." 2019 28th IEEE International Conference on Robot and Human Interactive Communication (RO-MAN). IEEE, 2019.
- Kapinus, Michal, et al. "Improved Indirect Virtual Objects Selection Methods for Cluttered Augmented Reality Environments on Mobile Devices." Proceedings of the 2022 ACM/IEEE International Conference on Human-Robot Interaction. 2022.
- Bambušek, Daniel, et al. "Handheld Augmented Reality: Overcoming Reachability Limitations by Enabling Temporal Switching to Virtual Reality." Proceedings of the 2022 ACM/IEEE International Conference on Human-Robot Interaction. 2022.
- Bambušek, Daniel, et al. How Do I Get There? Overcoming Reachability Limitations of Constrained Industrial Environments in Augmented Reality Applications. In: 2023 IEEE Conference Virtual Reality and 3D User Interfaces (VR). IEEE, 2023. p. 115-122.
- Kapinus, Michal, et al. ARCOR2: Framework for Collaborative End-User Management of Industrial Robotic Workplaces using Augmented Reality. arXiv preprint arXiv:2306.08464, 2023.


