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

# install python dependencies
pip install -r requirements.txt

################################################################################################################################
#install tor - Below lines taken from Bitcoin standup
#  To use source lines with https:// in /etc/apt/sources.list the apt-transport-https package is required. Install it with:
sudo apt install apt-transport-https
# We need to set up our package repository before you can fetch Tor. First, you need to figure out the name of your distribution:
DEBIAN_VERSION=$(lsb_release -c | awk '{ print $2 }')
# You need to add the following entries to /etc/apt/sources.list:
#cat >> /etc/apt/sources.list << EOF
#deb https://deb.torproject.org/torproject.org $DEBIAN_VERSION main
#deb-src https://deb.torproject.org/torproject.org $DEBIAN_VERSION main
#EOF
# Then add the gpg key used to sign the packages by running:
#sudo apt-key adv --recv-keys --keyserver keys.gnupg.net  74A941BA219EC810
#sudo wget -qO- https://deb.torproject.org/torproject.org/A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89.asc | gpg --import
#sudo gpg --export A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89 | apt-key add -
# Update system, install and run tor as a service
#sudo apt update
#sudo apt install tor deb.torproject.org-keyring
################################################################################################################################
mkdir /var/lib/tor/Spotbit
echo '# setup for Spotbit service' >> /etc/tor/torrc
echo 'HiddenServiceDir /var/lib/tor/Spotbit' >> /etc/tor/torrc
echo 'HiddenServicePort 80 127.0.0.1:5000' >> /etc/tor/torrc

# start the tor service after we're done
echo "starting tor"
systemctl restart tor.service

################################################################################################################################
# Copy the default config to file
mkdir ~/.spotbit
touch ~/.spotbit/spotbit.config
cat spotbit_example.config >> ~/.spotbit/spotbit.config

# show the URL of the hidden service
echo "hidden service onion address (located at /var/lib/tor/Spotbit):"
cat /var/lib/tor/Spotbit/hostname

