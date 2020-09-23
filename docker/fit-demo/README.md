
# FIT demo

This demo incorporates robots Dobot M1 and Dobot Magician. 

Contains services: arserver, execution, build, project and execution proxy 

## Uploading object_types to project service

```bash
docker run --rm --network="fit-demo_testitoff-robot-network" --env ARCOR2_PERSISTENT_STORAGE_URL=http://project:10000 arcor2/arcor2_upload_fit_demo:VERSION
```
Network has to be set to any network where project service is accessible. Instead of VERSION use desired version of arcor2_fit_demo package. 
