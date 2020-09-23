#!/bin/bash

# Install Spotbit script help

# help definition
function help () {

bold=$(tput bold)
normal=$(tput sgr0)
underline=$(tput smul)

cat <<-END

---------------------------------
${bold}Blockchain Commons Spotbit Install Script${normal}
---------------------------------

Contributor: jodobear

The "installSpotbit.sh" script configures the system to run the Spotbit server. You can install it on any Debian based system.

--------------------------------------
${bold}                Usage                 ${normal}
--------------------------------------


1. Edit the "installSpotbit.config" file. All the environment variables are defined there.
2. Run "installSpotbit.sh" file as root user like so: source installSpotbit.sh

NOTE: There is also a "installSpotbit.config.defaults" file which is used in case the "installSpotbit.config" is not present.



The script will do the following:

1. Setup the VPS Hostname, FQDN & Region if installing on VPS
2. Update system & set to autoupdate
3. Install ufw & gnupg2
4. Setup user "spotbit" with sudo access & set a password if probided.
5. Setup SSH keys & SSH IPs
6. Install & configure Tor & setup Hidden Service for Spotbit server.
7. Install Python 3.8 if not installed.
8. Install Python dependencies.
9. Copy spotbit config file to "~spotbit/.spotbit"
10. Move spotbit repo directory under user "spotbit"

END
}

help