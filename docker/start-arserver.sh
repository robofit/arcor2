#!/bin/bash  
cd /root/data/
python3 -m http.server 8888 &
cd /root
./arserver.pex
