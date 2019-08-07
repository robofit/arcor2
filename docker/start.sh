#!/bin/bash  

cd /root/arcor2
git pull
cd /root/arcor2_kinali
git pull
cd /root/arcor2_kinali/arcor2_kinali/arcor2_kinali/object_types
python upload.py
cd /root/arcor2/arcor2/user_objects
python upload.py
arcor2_manager --rpc-plugins arcor2_kinali.plugins/KinaliRpcPlugin &
sleep 5
cd /root/arcor2
arcor2_server