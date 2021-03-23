#!/bin/bash  


cd /root || exit
if [ "$ARCOR2_DOBOT_SIMULATOR" = true ] ; then
    ./dobot.pex -m
else 
	./dobot.pex
fi


#
#