
# FIT demo

This demo incorporates Dobot M1, Dobot Magician, a conveyor belt (connected to Magician), and Kinect Azure.

To run a simulation environment (where Dobot and Kinect services are started in mock mode), you can use just `docker compose up`. When running with the actual hardware, please use `docker compose -f docker-compose.yml -f docker-compose.lab.yml up`.

## Uploading ObjectTypes to Project service

Objects for fit-demo are uploaded with every start of the compose, but you can also do that manually:

```bash
docker run --rm --network="fit-demo-project-network" --env ARCOR2_PROJECT_SERVICE_URL=http://fit-demo-project:10000 arcor2/arcor2_upload_fit_demo:VERSION
```
The network has to be set to any network where the Project service is accessible. Instead of `VERSION`, use the desired version of the arcor2_fit_demo package. 

## Scaling of Calibration service

To run multiple instances of the Calibration service with some basic load balancing, you can run compose like this:

```bash
docker compose up --scale fit-demo-calibration=5
```
...where 5 is the number of instances.

## Second "instance"

If you need to run a second ARServer (and other services) on the same PC, you can use the following compose file. Please note that it does not contain robots.

```bash
docker compose -f docker-compose.2.yml up
```