
# FIT demo

This demo incorporates robots Dobot M1 and Dobot Magician. 

Contains services: arserver, execution, build, project and execution proxy

To run simulation environment (where Dobot services are started in mock mode) you can use just `docker-compose up`. When running with the actual hardware, please use `docker-compose -f docker-compose.yml -f docker-compose.lab.yml up`.

## Uploading object_types to project service

Objects for fit-demo are uploaded with every start of the compose but you can also do that manually:

```bash
docker run --rm --network="fit-demo-project-network" --env ARCOR2_PROJECT_SERVICE_URL=http://fit-demo-project:10000 arcor2/arcor2_upload_fit_demo:VERSION
```
Network has to be set to any network where project service is accessible. Instead of VERSION use desired version of arcor2_fit_demo package. 

## Scaling of calibration service

To run multiple instances of calibration service with some basic load balancing you can run docker-compose like this:

```bash
sudo docker-compose up --scale fit-demo-calibration=5
```
...where 5 is the number of instances.
