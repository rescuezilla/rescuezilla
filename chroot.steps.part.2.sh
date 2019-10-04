#!/bin/bash

set -x

# Non-interactive apt operations
DEBIAN_FRONTEND=noninteractive

# Extract the changed files archive
cd /
dpkg -i adeskbar*.deb
apt-get --yes -f install
apt-get install --yes python-wnck python-pyinotify python-alsaaudio python-vte python-xlib
rm -rf *.deb

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

# Remove upgraded or old linux kernels if present
ls /boot/vmlinuz-3.2.**-**-generic > list.txt
sum=$(cat list.txt | grep '[^ ]' | wc -l)
if [ $sum -gt 1 ]; then
  dpkg -l 'linux-*' | sed '/^ii/!d;/'"$(uname -r | sed "s/\(.*\)-\([^0-9]\+\)/\1/")"'/d;s/^[^ ]* [^ ]* \([^ ]*\).*/\1/;/[0-9]/!d' | xargs sudo apt-get -y purge
fi
rm list.txt

rm /var/lib/dbus/machine-id
rm /sbin/initctl
dpkg-divert --rename --remove /sbin/initctl

# Move downloaded apt packages and indexes to top-level chroot directory, to be
# extracted out of chroot and saved for subsequent builds.
mv /var/cache/apt/archives /var.cache.apt.archives
mv /var/lib/apt/lists /var.lib.apt.lists
# From `man apt-get`: "clears out the local repository of retrieved package
# files. It removes everything but the lock file from /var/cache/apt/archives/
# and /var/cache/apt/archives/partial/."
apt-get clean

rm -rf /tmp/*
rm /etc/resolv.conf
rm -rf /var/lib/apt/lists/????????*
umount -lf /proc
umount -lf /sys
umount -lf /dev/pts
