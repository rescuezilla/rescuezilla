#!/bin/bash

set -x

# Non-interactive apt operations
DEBIAN_FRONTEND=noninteractive

cd /


# Install Rescuezilla frontend, other rescuezilla packages and all dependencies.
DEB_PACKAGES=/*.deb
for f in $DEB_PACKAGES
do
  # gdebi installs deb files and resolves dependencies from the apt repositories.
  gdebi --non-interactive $f
  if [[ $? -ne 0 ]]; then
    echo "Error: Failed to install Rescuezilla deb packages."
    exit 1
  fi
done

# Delete the now-installed deb files from the chroot filesystem
rm /*.deb

update-alternatives --set x-terminal-emulator /usr/bin/xfce4-terminal
update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth /usr/share/plymouth/themes/rescuezilla-logo/rescuezilla-logo.plymouth 100
update-alternatives --set default.plymouth /usr/share/plymouth/themes/rescuezilla-logo/rescuezilla-logo.plymouth

update-initramfs -u

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

# Disable systemd's built-in NTP time synchronization service by manually masking it (`systemctl mask`)
# using a symlink. This timesyncd service always modifies the hardware clock, and there
# does not appear to be a way to prevent this service from modifying the hardware clock.
# See [1] for more discussion.
# [1] https://github.com/rescuezilla/rescuezilla/issues/107
rm /etc/systemd/system/systemd-timesyncd.service
ln -s /dev/null /etc/systemd/system/systemd-timesyncd.service

# Replace host system's resolv.conf with Google DNS
cat << EOF > /etc/resolv.conf
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF

rm -rf /tmp/*
rm -rf /var/lib/apt/lists/????????*
umount -lf /proc
umount -lf /sys
umount -lf /dev/pts

exit 0
