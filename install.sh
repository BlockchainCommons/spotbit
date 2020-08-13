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
# need to force python3.8 as well
# TODO: compile and install python3.8
pip3.8 install -r requirements.txt

################################################################################################################################
#install tor - Below lines taken from Bitcoin standup
#  To use source lines with https:// in /etc/apt/sources.list the apt-transport-https package is required. Install it with:
sudo apt install apt-transport-https
# We need to set up our package repository before you can fetch Tor. First, you need to figure out the name of your distribution:
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
################################################################################################################################
# Configure the Spotbit user
/usr/sbin/useradd -m -p `perl -e 'printf("%s\n,crypt($ARGV[0],"spotbit"))' "spotbit"` -g sudo -s /bin/bash/ spotbit
/usr/sbin/adduser spotbit sudo
echo "created spotbit user in sudo group"

mkdir /var/lib/tor/Spotbit
chown -R debian-tor:debian-tor /var/lib/tor/Spotbit
chmod 700 /var/lib/tor/Spotbit
echo '# setup for Spotbit service' >> /etc/tor/torrc
echo 'HiddenServiceDir /var/lib/tor/Spotbit' >> /etc/tor/torrc
echo 'HiddenServicePort 80 127.0.0.1:5000' >> /etc/tor/torrc
echo 'HiddenServiceVersion 3' >> /etc/tor/torrc

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
fi

# show the URL of the hidden service
echo "waiting 2 minutes for tor to finish bootstrapping."
sleep 2m
echo "hidden service onion address (located at /var/lib/tor/Spotbit):"
cat /var/lib/tor/Spotbit/hostname

