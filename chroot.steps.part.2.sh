#!/bin/bash

set -x

# Non-interactive apt operations
DEBIAN_FRONTEND=noninteractive

cd /
update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth /usr/share/plymouth/themes/redo-logo/redo-logo.plymouth 100
update-alternatives --set default.plymouth /usr/share/plymouth/themes/redo-logo/redo-logo.plymouth
update-initramfs -u

# Install localepurge, and use currently installed /etc/locale.nopurge config file, not package maintainer's version.
apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install --yes localepurge

# Explicitly run localepurge. The man page says localepurge "will be automagically invoked by dpkg upon completion of  any  apt
# installation  run". This did not happen in testing (possibly because of debconf/frontend Noninteractive mode).
localepurge

# Remove unused packages (such as old linux kernels, if present)
# 
# From `man apt-get`: autoremove is used to remove packages that were
# automatically installed to satisfy dependencies for other packages and are
# now no longer needed.
sudo apt-get --yes autoremove

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
