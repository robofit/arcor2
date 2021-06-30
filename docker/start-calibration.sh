#!/bin/bash  

cd /root || exit
if [ "$ARCOR2_CALIBRATION_SIMULATOR" = true ] ; then
    ./calibration.pex --mock
else
    ./calibration.pex -c "/root/calibration.yaml"
fi
