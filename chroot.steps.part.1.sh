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

# Clean out local repository of retrieved packages which "no longer be downloaded, and are largely useless."
# "This allows a cache to be maintained over a long period without it growing out of control."
apt-get autoclean

mkdir /var/lib/dbus
apt-get install --yes --no-install-recommends dbus
dbus-uuidgen > /var/lib/dbus/machine-id

dpkg-divert --local --rename --add /sbin/initctl
ln -s /bin/true /sbin/initctl

perl -p -i -e 's/^set compatible$/set nocompatible/g' /etc/vim/vimrc.tiny

apt-get upgrade --yes

# Ensure initramfs configuration file matches package maintainer's version during
# rebuild on ISO image, so that the build is fully unattended while avoiding
# another use of Dpkg::Options. See the other sed command below for original
# modification of initramfs.conf and the reason for the modification.
sed --in-place s/COMPRESS=gzip/COMPRESS=lz4/g /etc/initramfs-tools/initramfs.conf

# Packages specific to Rescuezilla 32-bit build (currently based Ubuntu 18.04 Bionic)
# Hardware Enablement (HWE, also called LTS Enablement Stack) [1] [2]
# https://wiki.ubuntu.com/Kernel/LTSEnablementStack
# https://ubuntu.com/about/release-cycle
pkgs_specific_to_32bit=("linux-generic-hwe-18.04"
                        "xserver-xorg-hwe-18.04"
                        "xserver-xorg-video-all-hwe-18.04"
                        "xserver-xorg-video-intel-hwe-18.04"
                        "xserver-xorg-video-qxl-hwe-18.04"
)

# Packages specific to Rescuezilla 64-bit build (currently based Ubuntu 20.04 Focal)
# TODO: Switch to Hardware Enablement (HWE, also called LTS Enablement Stack) [1] [2]
#       when it is released.
# https://wiki.ubuntu.com/Kernel/LTSEnablementStack
# https://ubuntu.com/about/release-cycle
pkgs_specific_to_64bit=("linux-generic-hwe-18.04"
                        "xserver-xorg-hwe-18.04"
                        "xserver-xorg-video-all-hwe-18.04"
                        "xserver-xorg-video-intel-hwe-18.04"
                        "xserver-xorg-video-qxl-hwe-18.04"
)

# Packages common to both  32-bit and 64-bit build
# TODO: Documentation each package with why these particular packages are present,
# TODO: and what they do.
common_pkgs=("discover"
             "laptop-detect"
             "os-prober"
             "casper"
             "lupin-casper"
             "xinit"
             "openbox"
             "x11-xserver-utils"
             "xterm"
             "network-manager-gnome"
             "plymouth-x11"
             "plymouth-label"
             "plymouth-theme-ubuntu-logo"
             "pcmanfm"
             "gvfs"
             "firefox"
             "firefox-locale-fr"
             "firefox-locale-de"
             "firefox-locale-es"
             "bluebird-gtk-theme"
             "gnome-icon-theme"
             "gnome-brave-icon-theme"
             "dmz-cursor-theme"
             "yad"
             "gpicview"
             "mousepad"
             "lxmenu-data"
             "arandr"
             "lxterminal"
             "lxpanel"
             "ttf-ubuntu-font-family"
             "alsamixergui"
             "volumeicon-alsa"
             "pm-utils"
             "libnotify-bin"
             "notify-osd"
             "notify-osd-icons"
             "time"
             "hdparm"
             "openssh-client"
             "libcapture-tiny-perl"
             "libfile-tee-perl"
             "libglib-perl"
             "libgtk2-perl"
             "libxml-simple-perl"
             "libsys-cpu-perl"
             "liblocale-maketext-lexicon-perl"
             "libmethod-signatures-simple-perl"
             "libstring-shellquote-perl"
             "pigz"
             "gtk2-engines-pixbuf"
             "beep"
             "rsync"
             "smartmontools"
             "gnome-disk-utility"
             "policykit-1-gnome"
             "policykit-desktop-privileges"
             "baobab"
             "gsettings-desktop-schemas"
             "gparted"
             "lshw-gtk"
             "testdisk"
             "gddrescue"
             "usb-creator-gtk"
             "wodim"
             "curlftpfs"
             "nmap"
             "cifs-utils"
             "libnotify-bin"
             "cryptsetup"
             "reiserfsprogs"
             "dosfstools"
             "ntfs-3g"
             "hfsutils"
             "reiser4progs"
             "jfsutils"
             "smbclient"
             "wget"
             "fsarchiver"
             "partclone"
             "exfat-fuse"
             "exfat-utils"
             "btrfs-progs"
             "udisks2-btrfs"
             "hfsplus"
             "hfsprogs"
             "f2fs-tools"
             "lvm2"
             "xfsdump"
             "xfsprogs"
             "udftools"
             "language-pack-gnome-fr-base"
             "language-pack-gnome-de-base"
             "language-pack-gnome-es-base"
)

if  [ "$ARCH" == "i386" ]; then
  apt_pkg_list=("${pkgs_specific_to_32bit[@]}" "${common_pkgs[@]}")
elif  [ "$ARCH" == "amd64" ]; then
  apt_pkg_list=("${pkgs_specific_to_64bit[@]}" "${common_pkgs[@]}")
else
  echo "Warning: unknown register width $ARCH"
  exit 1
fi

apt-get install --yes --no-install-recommends "${apt_pkg_list[@]}"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to install packages."
    exit 1
fi

# Install the packages that have custom configuration files managed in the
# source tree, and use non-interactive conflict resolution to choose those
# configuration files, not package maintainer's versions.  The non-interactive
# conflict resolutions means its the responsibility of the of the build script
# maintainer to periodically ensure the version-controlled configuration file
# hasn't does not become too old and out-of-date compared to the package
# maintainer's version.
#
apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install --yes slim

# Prevent "initramfs unpacking failed: Decoding failed" message on Ubuntu 19.10
# and Ubuntu 20.04 systems [1] [2]. Using gzip means supposedly slower boot
# than lz4 compression, but it's a worthwhile trade-off to prevent any 
# non-technical end-users from seeing an error message.
# [1] https://bugs.launchpad.net/ubuntu/+source/ubuntu-meta/+bug/1870260
# [2] https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1835660
sed --in-place s/COMPRESS=lz4/COMPRESS=gzip/g /etc/initramfs-tools/initramfs.conf

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
