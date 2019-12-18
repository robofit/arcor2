#!/bin/bash 
docker build -f Dockerfile-arserver -t arcor2/arcor2_arserver:`cat ../arcor2/VERSION`  ../ --build-arg version=`cat ../arcor2/VERSION`
docker build -f Dockerfile-build -t arcor2/arcor2_build:`cat ../arcor2/VERSION` --build-arg version=`cat ../arcor2/VERSION` ../
docker build -f Dockerfile-execution -t arcor2/arcor2_execution:`cat ../arcor2/VERSION` --build-arg version=`cat ../arcor2/VERSION` ../   