#!/bin/bash
# Spotbit Install Script - Blockchain Commons

set +ex

# If script not sourced, stop here
if [[ "$0" = "$BASH_SOURCE" ]]; then
    echo "This script must be sourced like so: \"source installSpotbit.sh\""
    return 1
fi

SCRIPTS_DIR="$PWD"

# message formatting variables
MESSAGE_PREFIX="-------Spotbit -"
bold=$(tput bold)
normal=$(tput sgr0)
underline=$(tput smul)

####
# Parsing Config file
####

config_read_file() {
    (grep -E "^${2}=" -m 1 "${1}" 2>/dev/null || echo "VAR=__UNDEFINED__") | head -n 1 | cut -d '=' -f 2-;
}

config_get() {
    val="$(config_read_file ./installSpotbit.config "${1}")";
    if [ "${val}" = "__UNDEFINED__" ]; then
        val="$(config_read_file ./installSpotbit.config.defaults "${1}")";
    fi
    printf -- "%s" "${val}";
}

# Environment Variables
# system
NOPROMPT="$(config_get NOPROMPT)"
USERPASSWORD="$(config_get USERPASSWORD)"
INSTALL_PYTHON38="$(config_get INSTALL_PYTHON38)"

# vps
VPS="$(config_get VPS)"
FQDN="$(config_get FQDN)"
HOSTNAME="$(config_get HOSTNAME)"
REGION="$(config_get REGION)"

# Tor & SSH
TOR_PUBKEY="$(config_get TOR_PUBKEY)"
SSH_KEY="$(config_get SSH_KEY)"
SYS_SSH_IP="$(config_get SYS_SSH_IP)"

####
# Parsing Arguments
####
PARAMS=""

while (( "$#" )); do
key="$1"
  case $key in
    -h|--help)
      source ./installSpotbit_help.sh
      return 2
      ;;
    -*|--*=) # unsupported flags
      echo "Error: Unsupported flag $1" >&2
      source ./installSpotbit_help.sh
      return 3
      ;;
    *) # preserve positional arguments
      PARAMS="$PARAMS $1"
      shift 1
      ;;
  esac
done
set -- "$PARAMS"  # set positional parameters in order


####
# 0. Force check for root
####

# if you are not logged in as root then the script will not execute
echo "
----------------
$MESSAGE_PREFIX Checking if logged in as root.
----------------"
if ! [ "$(id -u)" == 0 ]; then
  echo "$MESSAGE_PREFIX You need to be logged in as root!"
  return 2

fi
echo "$MESSAGE_PREFIX Logged in as root. Continuing with installation.
----------------
"
# Output stdout and stderr to ~root files
exec > >(tee -a /root/spotbit.log) 2> >(tee -a /root/spotbit.log /root/spotbit.err >&2)

####
# 1. Update Hostname and set timezone
####
# source vps setup script
if "$VPS"; then
  IPADDR=""
  # Check for FQDN & HOSTNAME if --vps
  if "$VPS" && [[ -z "$HOSTNAME" ]] || [[ "$HOSTNAME" == "__UNDEFINED__" ]]; then
    echo "
    $MESSAGE_PREFIX Hostname not provided.
    "
    while  [ -z "$HOSTNAME" ]; do
      read -rp "Enter hostname of the server: " HOSTNAME
    done
  fi

  if "$VPS" && [[ -z "$FQDN" ]] || [[ "$FQDN" == "__UNDEFINED__" ]]; then
    echo "
    $MESSAGE_PREFIX FQDN not provided. Please provide a domain name."
    while [ -z "$FQDN" ]; do
      read -rp "Enter the fqdn of the server: " FQDN
    done
  fi

  if "$VPS" && [[ -z "$REGION" ]] || [[ "$REGION" == "__UNDEFINED__" ]]; then
  echo "
  $MESSAGE_PREFIX Region of the server not provided. It is required to set the timezone.
  "
    while [ -z "$REGION" ]; do
      read -rp "Enter the region of the server: " REGION
    done
  fi

  echo "$HOSTNAME" > /etc/hostname

  /bin/hostname "$HOSTNAME"

  # Set the variable $IPADDR to the IP address the new Linode receives.
  apt-get -qq -y install net-tools
  IPADDR=$(/sbin/ifconfig eth0 | awk '/inet / { print $2 }' | sed 's/addr://')

  echo "$MESSAGE_PREFIX Set hostname as $FQDN ($IPADDR)"
  echo "
    ***********************
      $MESSAGE_PREFIX TODO: Put $FQDN with IP $IPADDR in your main DNS file.
    ***********************
  "
  echo "$MESSAGE_PREFIX Set Time Zone to $REGION"
  echo $REGION > /etc/timezone
  cp /usr/share/zoneinfo/${REGION} /etc/localtime

  echo "
    $MESSAGE_PREFIX Hostname, IP address and timezon are set. Put $FQDN with IP $IPADDR in your main DNS file.
    "
  # Add localhost aliases

  echo "127.0.0.1   localhost" > /etc/hosts
  echo "127.0.1.1   $FQDN $HOSTNAME" >> /etc/hosts

  echo "$MESSAGE_PREFIX - Set localhost"
fi


# Display script configuration
echo "
---------SETUP---------
Parameters Passed:

System
------
NOPROMPT..........: $NOPROMPT
USERPASSWORD......: $USERPASSWORD
INSTALL_PYTHON38..: $INSTALL_PYTHON38

VPS
---
VPS...........: $VPS
FQDN..........: $FQDN
HOSTNAME......: $HOSTNAME
REGION........: $REGION

Tor & SSH
----------
TOR_PUBKEY....: $TOR_PUBKEY
SSH_KEY.......: $SSH_KEY
SYS_SSH_IP....: $SYS_SSH_IP
"

# prompt user before continuing with installation
if ! "$NOPROMPT"; then
  read -rp  "Continue with installation? (Y/n): " confirm
  if [[ "$confirm" != [yY] ]]; then
    echo "Entered $confirm. Exiting.."
    return 4
  fi
fi


####
# 2. Update Debian, Set autoupdate and Install Dependencies (ufw)
####
echo "
----------------
$MESSAGE_PREFIX Starting Debian updates; this will take a while!
----------------
"

# Make sure all packages are up-to-date
apt-get update
apt-get upgrade -y
apt-get dist-upgrade -y

# Set system to automatically update
echo "
----------------
$MESSAGE_PREFIX setting system to automatically update
----------------
"
echo "unattended-upgrades unattended-upgrades/enable_auto_updates boolean true" | debconf-set-selections
apt-get -y install unattended-upgrades
echo "
$MESSAGE_PREFIX Debian Packages updated
"
# Get uncomplicated firewall and deny all incoming connections except SSH
if [ -z "$(which ufw)" ]; then
  echo "
$MESSAGE_PREFIX Installing ufw & gnuppg2
  "
  apt-get install ufw gnupg2 -y
fi

ufw allow ssh
ufw --force enable

echo "
$MESSAGE_PREFIX ufw is installed and enabled.
"


####
# 3. Setup User & SSH
####
if [ -z "$(cat /etc/shadow | grep spotbit)" ] && [ -z "$(groups spotbit)" ]; then
  echo "
----------------
  $MESSAGE_PREFIX Creating user spotbit
----------------
  "
  # Create "spotbit" group & user with optional password and give them sudo capability
  /usr/sbin/groupadd spotbit
  /usr/sbin/useradd -m -p `perl -e 'printf("%s\n",crypt($ARGV[0],"password"))' "$USERPASSWORD"` -g sudo -s /bin/bash spotbit
  /usr/sbin/adduser spotbit sudo
  /usr/sbin/adduser spotbit spotbit

  echo "
$MESSAGE_PREFIX User spotbit created with sudo access.
  "
else
  echo "
  ----------------
  $MESSAGE_PREFIX User spotbit already exists.
  ----------------"
fi

# Setup SSH Key if the user added one as an argument
if [ -n "$SSH_KEY" ] && [[ "$SSH_KEY" != "__UNDEFINED__" ]]; then
  mkdir ~spotbit/.ssh
  echo "$SSH_KEY" >> ~spotbit/.ssh/authorized_keys
  chown -R spotbit ~spotbit/.ssh
  echo "
----------------
$MESSAGE_PREFIX Added .ssh key to spotbit.
----------------
  "
fi

# Setup SSH allowed IP's if the user added any as an argument
if [ -n "$SYS_SSH_IP" ] && [[ "$SYS_SSH_IP" != "__UNDEFINED__" ]]; then
  echo "sshd: $SYS_SSH_IP" >> /etc/hosts.allow
  echo "sshd: ALL" >> /etc/hosts.deny
  echo "
----------------
$MESSAGE_PREFIX Limited SSH access.
----------------
  "
else
  echo "
  ****************
  $MESSAGE_PREFIX WARNING: Your SSH access is not limited; this is a major security hole!
  ****************
  "
fi


####
# 4. Install latest stable tor
####

# Download tor
echo "
----------------
  $MESSAGE_PREFIX Installing Tor
----------------
"
#  To use source lines with https:// in /etc/apt/sources.list the apt-transport-https package is required. Install it with:
if [ -z "$(which apt-transport-https)" ]; then
  apt-get install apt-transport-https -y
  echo "
$MESSAGE_PREFIX apt-transport-https installed
  "
fi

# Install torsocks
if [ -z "$(which torsocks)" ]; then
  apt-get install torsocks -y
  echo "
$MESSAGE_PREFIX torsocks installed
  "
fi

# We need to set up our package repository before you can fetch Tor. First, you need to figure out the name of your distribution:
DEBIAN_VERSION=$(lsb_release -c | awk '{ print $2 }')

# You need to add the following entries to /etc/apt/sources.list:
cat >> /etc/apt/sources.list << EOF
deb https://deb.torproject.org/torproject.org $DEBIAN_VERSION main
deb-src https://deb.torproject.org/torproject.org $DEBIAN_VERSION main
EOF

# Then add the gpg key used to sign the packages by running:
# apt-key adv --recv-keys --keyserver keys.gnupg.net  74A941BA219EC810
wget -qO- https://deb.torproject.org/torproject.org/A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89.asc | gpg --import
gpg --export A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89 | apt-key add -

# Update system, install and run tor as a service
apt update
apt install tor deb.torproject.org-keyring -y

# Setup hidden service
sed -i -e 's/#ControlPort 9051/ControlPort 9051/g' /etc/tor/torrc
sed -i -e 's/#CookieAuthentication 1/CookieAuthentication 1/g' /etc/tor/torrc
# for c-lightning
sed -i -e 's/#CookieAuthFileGroupReadable 1/CookieAuthFileGroupReadable 1/g' /etc/tor/torrc
sed -i -e 's/## address y:z./## address y:z.\
\
HiddenServiceDir \/var\/lib\/tor\/spotbit\/\
HiddenServiceVersion 3\
HiddenServicePort 80 127.0.0.1:5000/g' /etc/tor/torrc

mkdir /var/lib/tor/spotbit
chown -R debian-tor:debian-tor /var/lib/tor/spotbit
chmod 700 /var/lib/tor/spotbit

# Add spotbit to the tor group so that the tor authentication cookie can be read by bitcoind
sudo usermod -a -G debian-tor spotbit

# Restart tor to create the HiddenServiceDir
sudo systemctl restart tor


if [[ -n "$(systemctl is-active tor) | grep active" ]]; then
echo "
$MESSAGE_PREFIX Tor installed and successfully started
"
fi

# add V3 authorized_clients public key if one exists
if [[ "$TOR_PUBKEY" != "" ]] && [[ "$TOR_PUBKEY" != "__UNDEFINED__" ]]; then
  # create the directory manually incase tor.service did not restart quickly enough
  mkdir /var/lib/tor/spotbit/authorized_clients

  # need to assign the owner
  chown -R debian-tor:debian-tor /var/lib/tor/spotbit/authorized_clients

  # Create the file for the pubkey
  touch /var/lib/tor/spotbit/authorized_clients/gordian.auth

  # Write the pubkey to the file
  echo "$TOR_PUBKEY" > /var/lib/tor/spotbit/authorized_clients/gordian.auth

  # Restart tor for authentication to take effect
  sudo systemctl restart tor.service

  echo "
  $MESSAGE_PREFIX Successfully added Tor V3 authentication
  "
fi


####
# 5. Install python & python dependencies
####
if "$INSTALL_PYTHON38"; then
  echo "
  ----------------
  $MESSAGE_PREFIX Installing python 3.8
  ----------------
"
  apt-get install build-essential checkinstall -y
  apt-get install libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev -y
  mkdir ~spotbit/downloads
  chown -R spotbit ~spotbit/downloads
  sudo -u spotbit wget --progress=bar:force https://www.python.org/ftp/python/3.8.5/Python-3.8.5.tgz -O ~spotbit/downloads/Python-3.8.5.tgz
  cd ~spotbit/downloads
  tar xzf Python-3.8.5.tgz
  cd Python-3.8.5
  ./configure --enable-optimizations
  make altinstall # altinstall to prevent replacing default python binary at /usr/bin/python
  if ! [[ -z "$(python3.8 -V)" ]]; then
    echo "
    $MESSAGE_PREFIX installed $(python3.8 -V)"
  fi
fi

cd "$SCRIPTS_DIR"

echo "
----------------
$MESSAGE_PREFIX Installing python dependencies
----------------
"
python3.8 -m pip install -r requirements.txt

cd "$SCRIPTS_DIR"

####
# 6. Copy spotbit.config
####
# Copy the default config to file
if test -f "/home/spotbit/.spotbit/spotbit.config"; then
  echo "configs already configured"
else
  mkdir /home/spotbit/.spotbit
  chown -R spotbit /home/spotbit/.spotbit
  touch /home/spotbit/.spotbit/spotbit.config
  cat spotbit_example.config >> /home/spotbit/.spotbit/spotbit.config
fi


####
# 7. Setup systemd service
####

sudo cat > /etc/systemd/system/spotbit.service << EOF
# It is not recommended to modify this file in-place, because it will
# be overwritten during package upgrades. If you want to add further
# options or overwrite existing ones then use
# $ systemctl edit spotbit.service
# See "man systemd.service" for details.

[Unit]
Description=Spotbit
Requires=tor.service
After=tor.service

[Service]
ExecStart=/usr/local/bin/python3.8 /home/spotbit/spotbit/server.py

# Process management
####################
Type=simple
PIDFile=/run/spotbit/spotbit.pid
Restart=on-failure

# Directory creation and permissions
####################################
# Run as spotbit:spotbit
User=spotbit
Group=spotbit
# /run/spotbit
RuntimeDirectory=spotbit
RuntimeDirectoryMode=0710

# Hardening measures
####################
# Provide a private /tmp and /var/tmp.
PrivateTmp=true
# Mount /usr, /boot/ and /etc read-only for the process.
ProtectSystem=full
# Disallow the process and all of its children to gain
# new privileges through execve().
NoNewPrivileges=true
# Use a new /dev namespace only populated with API pseudo devices
# such as /dev/null, /dev/zero and /dev/random.
PrivateDevices=true
# Deny the creation of writable and executable memory mappings.
MemoryDenyWriteExecute=true

[Install]
WantedBy=multi-user.target
EOF


# restart tor & enable spotbit service
sudo systemctl restart tor
sleep 4
sudo systemctl enable spotbit.service
sudo systemctl start spotbit.service


# move spotbit repo directory under spotbit user
cp -r $SCRIPTS_DIR ~spotbit/
chown -R spotbit ~spotbit/spotbit
cd ~spotbit/spotbit
rm -rf $SCRIPTS_DIR
# show the URL of the hidden service & set it in bashrc
SPOTBIT_ONION=$(cat /var/lib/tor/spotbit/hostname)
echo "export ONION=$SPOTBIT_ONION" >> .bashrc
echo "
*******************************************************************************
$MESSAGE_PREFIX Spotbit has been configured. Start spotbit server like so:

sudo systemctl start spotbit

Then access it on clearnet at:
http://localhost:5000

OR on it's onion(Tor) address (located at /var/lib/tor/spotbit/hostname):
$SPOTBIT_ONION
*******************************************************************************
"
