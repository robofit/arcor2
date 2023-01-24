#!/usr/bin/env bash

set -e # stop script when error occurs
apt-get update
apt-get install -y gnupg2 libgl1-mesa-glx libglib2.0-0
curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/18.04/prod bionic main" >>/etc/apt/sources.list # 20.04 is not officially supported but it works like this
apt-get update
export DEBIAN_FRONTEND="noninteractive"
echo 'libk4a1.4 libk4a1.4/accepted-eula-hash string 0f5d5c5de396e4fee4c0753a21fee0c1ed726cf0316204edda484f08cb266d76' | debconf-set-selections
echo 'libk4a1.4 libk4a1.4/accept-eula boolean true' | debconf-set-selections
echo 'libk4abt1.1 libk4abt1.1/accepted-eula-hash string 03a13b63730639eeb6626d24fd45cf25131ee8e8e0df3f1b63f552269b176e38' | debconf-set-selections
apt-get install -y libk4a1.4 libk4a1.4-dev libk4abt1.1 libk4abt1.1-dev
