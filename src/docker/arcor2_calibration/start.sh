#!/bin/bash

cd /root || exit
if [ "$ARCOR2_CALIBRATION_MOCK" = true ]; then
	./calibration.pex --mock
else
	./calibration.pex -c "/root/calibration.yaml"
fi
