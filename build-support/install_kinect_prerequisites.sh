curl -sSL https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
sudo apt-add-repository https://packages.microsoft.com/ubuntu/"$(lsb_release -rs)"/prod
sudo apt-get update
export DEBIAN_FRONTEND="noninteractive"
echo 'libk4a1.4 libk4a1.4/accepted-eula-hash string 0f5d5c5de396e4fee4c0753a21fee0c1ed726cf0316204edda484f08cb266d76' | sudo debconf-set-selections
echo 'libk4a1.4 libk4a1.4/accept-eula boolean true' | sudo debconf-set-selections
sudo apt-get install -y libk4a1.4 libk4a1.4-dev
sudo wget https://raw.githubusercontent.com/microsoft/Azure-Kinect-Sensor-SDK/develop/scripts/99-k4a.rules -P /etc/udev/rules.d/
sudo udevadm control --reload-rules && udevadm trigger