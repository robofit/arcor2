
# Kinali demo

This demo incorporates robot Aubo i5 and several other Kinali objects. 

## Uploading object_types to project service

```bash
docker run --rm --network="kinali-demo_testitoff-project-network" --env ARCOR2_PROJECT_SERVICE_URL=http://project:10000 arcor2/arcor2_upload_kinali:VERSION
```
Network has to be set to any network where project service is accessible. Instead of VERSION use desired version of arcor2_kinali package. 
