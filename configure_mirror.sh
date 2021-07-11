#!/bin/bash
# Use netselect to configure the closes and hopefully fasted mirror for apt pacakge downloads

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please consult build instructions."
   exit 1
fi
## ensure netselect is installed
NETSELECT_x64=http://ftp.au.debian.org/debian/pool/main/n/netselect/netselect_0.3.ds1-29_amd64.deb
NETSELECT_FILE=netselect_0.3.ds1-29_amd64.deb

wget $NETSELECT_x64
dpkg -i $NETSELECT_FILE

# figure out the fastest / closest mirror to wherever you are
FASTMIRROR=`netselect -s 10 -t 20 $(wget -qO - mirrors.ubuntu.com/mirrors.txt) | head -1 | cut -d" " -f5`

## fix up the ubuntu server addresses to speed downloads
sed --in-place "s#http://archive.ubuntu.com/ubuntu#$FASTMIRROR#g" build.sh

# apparently sed doesnt like sub directories
cd src/livecd/chroot/etc/apt
sed --in-place "s#http://archive.ubuntu.com/ubuntu#$FASTMIRROR#g" sources.list
