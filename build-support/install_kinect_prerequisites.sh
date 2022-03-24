set -e  # stop script when error occurs
curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
echo "deb https://packages.microsoft.com/ubuntu/18.04/prod bionic main" >> /etc/apt/sources.list  # 20.04 is not officially supported but it works like this
apt-get update
export DEBIAN_FRONTEND="noninteractive"
echo 'libk4a1.4 libk4a1.4/accepted-eula-hash string 0f5d5c5de396e4fee4c0753a21fee0c1ed726cf0316204edda484f08cb266d76' | debconf-set-selections
echo 'libk4a1.4 libk4a1.4/accept-eula boolean true' | debconf-set-selections
apt-get install -y libk4a1.4 libk4a1.4-dev