#!/bin/bash  
cd /root/data/ || exit
python3 -m http.server 8888 &
cd /root || exit
./arserver.pex