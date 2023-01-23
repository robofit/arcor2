#!/bin/bash

cd /root || exit
if [ "$ARCOR2_CALIBRATION_MOCK" = true ]; then
	/bin/app/pex --mock
else
	/bin/app/pex -c "/root/calibration.yaml"
fi
