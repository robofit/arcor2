#!/bin/bash  

cd /root/arcor2/arcor2/user_objects || exit
python upload.py
arcor2_manager &
sleep 5
arcor2_server
