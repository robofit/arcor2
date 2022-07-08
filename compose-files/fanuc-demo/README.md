
# Fanuc demo

This demo incorporates one Fanuc robot. 

Contains services: arserver, execution, build, project and execution proxy

To start it, use `docker-compose up`.

## Uploading object_types to project service

Objects for the demo are uploaded with every start of the compose file but you can also do that manually:

```bash
docker run --rm --network="fanuc-demo-project-network" --env ARCOR2_PROJECT_SERVICE_URL=http://fanuc-demo-project:10000 arcor2/arcor2_fanuc_upload_object_types:VERSION
```
Network has to be set to any network where project service is accessible. Instead of VERSION use desired version of `arcor2_fanuc` package. 

## Scaling of calibration service

To run multiple instances of calibration service with some basic load balancing you can run docker-compose like this:

```bash
sudo docker-compose up --scale fanuc-demo-calibration=5
```
...where 5 is the number of instances.
