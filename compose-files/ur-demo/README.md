# UR Demo

The UR Web API service itself is documented [here](https://github.com/robofit/arcor2/blob/master/src/python/arcor2_ur/README.md). 

To use it with simulator, run:

```bash
docker compose -f docker-compose.yml -f docker-compose.sim.yml up
```

For the real robot, use the following command:

```bash
docker compose -f docker-compose.yml -f docker-compose.lab.yml up
```

In both cases, it is necessary to create a program for external control in the robot. With simulator, one can access robot's interface (Polyscope) using the VNC on [http://localhost:6080/vnc.html](http://localhost:6080/vnc.html).