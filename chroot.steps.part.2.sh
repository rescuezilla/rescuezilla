#!/bin/bash

set -x

# Non-interactive apt operations
DEBIAN_FRONTEND=noninteractive

# Extract the changed files archive
cd /
dpkg -i /packages/*.deb
apt-get --yes -f install
dpkg -i /packages/partclone*
tar zxvf /packages/fsarchiver-bin-0.6.12.tar.gz -C /packages
mv /packages/fsarchiver-bin-0.6.12/fsarchiver /sbin/
rm -rf /packages

update-alternatives --install /lib/plymouth/themes/default.plymouth default.plymouth /lib/plymouth/themes/redo-logo/redo-logo.plymouth 100
update-alternatives --set default.plymouth /lib/plymouth/themes/redo-logo/redo-logo.plymouth
update-initramfs -u

# Create localepurge config file with list of locales to keep.
cat << EOF > /etc/locale.nopurge
####################################################
# This is the configuration file for localepurge(8).
####################################################

####################################################
# Uncommenting this string enables removal of localized 
# man pages based on the configuration information for
# locale files defined below:

MANDELETE

####################################################
# Uncommenting this string causes localepurge to simply delete
# locales which have newly appeared on the system without
# bothering you about it:

DONTBOTHERNEWLOCALE

####################################################
# Uncommenting this string enables display of freed disk
# space if localepurge has purged any superfluous data:

SHOWFREEDSPACE

#####################################################
# Commenting out this string enables faster but less
# accurate calculation of freed disk space:

#QUICKNDIRTYCALC

#####################################################
# Commenting out this string disables verbose output:

#VERBOSE

#####################################################
# Following locales won't be deleted from this system
# after package installations done with apt-get(8):

en
en_US
en_US.UTF-8
EOF

# Install localepurge, and use currently installed /etc/locale.nopurge config file, not package maintainer's version.
apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install --yes localepurge

# Explicitly run localepurge. The man page says localepurge "will be automagically invoked by dpkg upon completion of  any  apt
# installation  run". This did not happen in testing (possibly because of debconf/frontend Noninteractive mode).
localepurge

rm /var/lib/dbus/machine-id
rm /sbin/initctl
dpkg-divert --rename --remove /sbin/initctl
apt-get clean
rm -rf /tmp/*
rm /etc/resolv.conf
rm -rf /var/lib/apt/lists/????????*
umount -lf /proc
umount -lf /sys
umount -lf /dev/pts
