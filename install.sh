#!/bin/bash

# Install script for Spotbit
# By Christian Murray
# Blockchain Commons
# To run this script, make it executable using `chmod +x install.sh` then `./install.sh`
# This script is intended for debian based systems with bash as the default shell

# Check if the user running the script is root - taken from bitcoin standup
if ! [ "$(id -u)" = 0 ]
then
  echo "$0 - You need to be logged in as root!"
  exit 1

fi

#  To use source lines with https:// in /etc/apt/sources.list the apt-transport-https package is required. Install it with:
# install the dependencies to build python3.8 on debian
sudo apt install apt-transport-https build-essential wget python3-openssl zlib1g-dev lsb-release libssl-dev libsqlite3-dev libffi-dev
################################################################################################################################
# install python 3.8 if its not already
PYTHON_VERSION=$(python3 --version | cut -c 8-12)
if [ "$PYTHON_VERSION" != "3.8.0" ]
then
  echo "Python3 is being upgraded to 3.8"
  wget https://www.python.org/ftp/python/3.8.0/Python-3.8.0.tgz
  tar -xvf Python-3.8.0.tgz
  cd Python-3.8.0
  ./configure
  make
  sudo make install 
  # set python3.8 to the default python3 and move the old python3 to a different location
  sudo cp /usr/bin/python3 /usr/bin/python$PYTHON_VERSION
  sudo cp /usr/bin/python3.8 /usr/bin/python3
  echo "done"
fi
################################################################################################################################

# install python dependencies
# need to force python3.8 as well
# TODO: compile and install python3.8
echo "installing python dependencies..."
pip3 install -r ./requirements.txt
echo "done"

################################################################################################################################
#install tor - Below lines taken from Bitcoin standup
# We need to set up our package repository before you can fetch Tor. First, you need to figure out the name of your distribution:
echo "installing tor..."
DEBIAN_VERSION=$(lsb_release -c | awk '{ print $2 }')
# You need to add the following entries to /etc/apt/sources.list:
cat >> /etc/apt/sources.list << EOF
deb https://deb.torproject.org/torproject.org $DEBIAN_VERSION main
deb-src https://deb.torproject.org/torproject.org $DEBIAN_VERSION main
EOF
# Then add the gpg key used to sign the packages by running:
sudo apt-key adv --recv-keys --keyserver keys.gnupg.net  74A941BA219EC810
sudo wget -qO- https://deb.torproject.org/torproject.org/A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89.asc | gpg --import
sudo gpg --export A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89 | apt-key add -
# Update system, install and run tor as a service
sudo apt update
sudo apt install tor deb.torproject.org-keyring
echo "done"
################################################################################################################################
# Configure the Spotbit user
/usr/sbin/useradd -m -p `perl -e 'printf("%s\n",crypt($ARGV[0],"spotbit"))' "spotbit"` -g sudo -s /bin/bash spotbit
/usr/sbin/adduser spotbit sudo
echo "created spotbit user in sudo group"
# Use sed to setup torrc so that the install script can be run multiple times without causing issues (taken from blockchain commons bitcoin standup scripts)
echo "configuring tor..."
sed -i -e 's/#ControlPort 9051/ControlPort 9051/g' /etc/tor/torrc
sed -i -e 's/#CookieAuthentication 1/CookieAuthentication 1/g' /etc/tor/torrc
sed -i -e 's/## address y:z./## address y:z.\
\
HiddenServiceDir \/var\/lib\/tor\/Spotbit\/\
HiddenServiceVersion 3\
HiddenServicePort 80 127.0.0.1:5000/g' /etc/tor/torrc
mkdir /var/lib/tor/Spotbit
chown -R debian-tor:debian-tor /var/lib/tor/Spotbit
chmod 700 /var/lib/tor/Spotbit
echo "done"

# add a systemd service for spotbit (created by @fonta1n3)
echo "creating systemd service..."
cp ./spotbit.service /etc/systemd/system/
echo "done"

# start the tor service after we're done
echo "starting tor"
systemctl daemon-reload
service tor stop
service tor start

################################################################################################################################
# Copy the default config to file
if test -f "/home/spotbit/.spotbit/spotbit.config"; then
  echo "configs already configured"
else
  mkdir /home/spotbit/.spotbit
  touch /home/spotbit/.spotbit/spotbit.config
  cat spotbit_example.config >> /home/spotbit/.spotbit/spotbit.config
  echo "You are currently using the default config. To change this, edit /home/spotbit/.spotbit/spotbit.config"
fi

# move source code to the spotbit user dir
echo "copying source to /home/spotbit/source..."
sudo mkdir /home/spotbit/source
cp -r ./* /home/spotbit/source/
systemctl daemon-reload
echo "done"

python3 ./configure.py
# add spotbit to the root group and make its source dir owned by this group
sudo gpasswd -a spotbit root
sudo chown -R spotbit:root /home/spotbit/source
# show the URL of the hidden service
echo "waiting 2 minutes for tor to finish bootstrapping."
sleep 2m
echo "hidden service onion address (located at /var/lib/tor/Spotbit):"
cat /var/lib/tor/Spotbit/hostname

