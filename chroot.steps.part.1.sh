#!/bin/bash
#
# Commands that occur within the chroot. That is, modifying what will become the root filesystem of the live CD
# using the commands present within the live CD.

set -x

APT_SOURCES_CHECKSUM=$(mktemp --suffix .apt.sources.checksum)

# Prepare the chroot environment
mount none -t proc /proc
mount none -t sysfs /sys
mount none -t devpts /dev/pts

export HOME=/root
export LC_ALL=C

# Ensure all Dockerfile package installation operations are non-interactive, DEBIAN_FRONTEND=noninteractive is insufficient [1]
# [1] https://github.com/phusion/baseimage-docker/issues/58
echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

sha1sum /etc/apt/sources.list /etc/apt/sources.list.d/* > $APT_SOURCES_CHECKSUM
if [ ! -d "/var/lib/apt/lists.cache" ] ; then
    # Must update apt package indexes if there is nothing cached.
    apt-get update
else
    # Even with a cache, still need to update if sources.list has changed
    diff $APT_SOURCES_CHECKSUM /var/lib/apt/lists.cache/apt.sources.checksum.txt
    if [ $? -ne 0 ]; then
        apt-get update
    else 
        rm -rf /var/lib/apt/lists
        mv /var/lib/apt/lists.cache /var/lib/apt/lists
    fi
fi
mv $APT_SOURCES_CHECKSUM /var/lib/apt/lists/apt.sources.checksum.txt

mkdir /var/lib/dbus
apt-get install --yes --no-install-recommends dbus
dbus-uuidgen > /var/lib/dbus/machine-id

dpkg-divert --local --rename --add /sbin/initctl
ln -s /bin/true /sbin/initctl

perl -p -i -e 's/^set compatible$/set nocompatible/g' /etc/vim/vimrc.tiny

apt-get upgrade --yes

# Install packages
apt-get install --yes --no-install-recommends discover \
                                              laptop-detect \
                                              os-prober \
                                              linux-generic \
                                              casper \
                                              lupin-casper \
                                              xinit \
                                              openbox \
                                              obconf \
                                              xserver-xorg \
                                              x11-xserver-utils \
                                              xterm \
                                              network-manager-gnome \
                                              plymouth-x11 \
                                              plymouth-label \
                                              plymouth-theme-ubuntu-logo \
                                              pcmanfm \
                                              gvfs \
                                              chromium-browser \
                                              bluebird-gtk-theme \
                                              gnome-icon-theme \
                                              gnome-brave-icon-theme \
                                              dmz-cursor-theme \
                                              maximus \
                                              yad \
                                              gpicview \
                                              leafpad \
                                              lxmenu-data \
                                              arandr \
                                              lxterminal \
                                              lxpanel \
                                              ttf-ubuntu-font-family \
                                              alsamixergui \
                                              volumeicon-alsa \
                                              pm-utils \
                                              libnotify-bin \
                                              notify-osd \
                                              notify-osd-icons \
                                              time \
                                              hdparm \
                                              openssh-client \
                                              libglib-perl \
                                              libgtk2-perl \
                                              libxml-simple-perl \
                                              gtk2-engines-pixbuf \
                                              beep \
                                              rsync \
                                              smartmontools \
                                              gnome-disk-utility \
                                              policykit-1-gnome \
                                              policykit-desktop-privileges \
                                              baobab \
                                              gsettings-desktop-schemas \
                                              gparted \
                                              lshw-gtk \
                                              testdisk \
                                              gddrescue \
                                              usb-creator-gtk \
                                              wodim \
                                              curlftpfs \
                                              nmap \
                                              cifs-utils \
                                              libnotify-bin \
                                              cryptsetup \
                                              reiserfsprogs \
                                              dosfstools \
                                              ntfs-3g \
                                              hfsutils \
                                              reiser4progs \
                                              jfsutils \
                                              smbclient \
                                              wget \
                                              fsarchiver \
                                              partclone

# Create empty config file for the network-manager service to manage all
# network devices. This is required for nm-applet to display network devices,
# and avoid it displaying a "device not managed" error. [1]
#                                              
# [1] https://askubuntu.com/a/893614/394984
touch /etc/NetworkManager/conf.d/10-globally-managed-devices.conf

ln -s /usr/bin/pcmanfm /usr/bin/nautilus
gconftool-2 --set /apps/maximus/undecorate --type BOOL false
rm /usr/bin/{rpcclient,smbcacls,smbclient,smbcquotas,smbget,smbspool,smbtar}
rm /usr/share/icons/*/icon-theme.cache
rm -rf /usr/share/doc
rm -rf /usr/share/man
rm -rf /etc/network/if-up.d/ntpdate
