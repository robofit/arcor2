#!/bin/bash 
#VERSION=`python3 ../setup.py --version`
VERSION='0.8.0rc3'
#docker image push arcor2/arcor2_base:$VERSION
docker image push arcor2/arcor2_arserver:`cat ../src/python/arcor2_arserver/VERSION`
docker image push arcor2/arcor2_execution:`cat ../src/python/arcor2_execution/VERSION`
docker image push arcor2/arcor2_execution_proxy:`cat ../src/python/arcor2_execution_proxy/VERSION`
docker image push arcor2/arcor2_build:`cat ../src/python/arcor2_build/VERSION`
docker image push arcor2/arcor2_mocks:`cat ../src/python/arcor2_mocks/VERSION`
#docker image push arcor2/arcor2_devel:`cat ../src/python/arcor2_arserver/VERSION`
