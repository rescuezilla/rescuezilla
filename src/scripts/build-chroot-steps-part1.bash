#!/bin/bash
#
# Commands that occur within the chroot. That is, modifying what will become the root filesystem of the live CD
# using the commands present within the live CD.

set -x

source pkgs.list 

APT_SOURCES_CHECKSUM=$(mktemp --suffix .apt.sources.checksum)

# Prepare the chroot environment
mount none -t proc /proc
mount none -t sysfs /sys
mount none -t devpts /dev/pts

export HOME=/root
export LC_ALL=C

# By default, Ubuntu puts a laptop to sleep whenever the lid is closed.
# Users have requested the Rescuezilla operation continue even if a laptop is closed
update_logind_conf_to_ignore_laptop_lid_switch() {
    sed --in-place 's/^[#]HandleLidSwitch=.*/HandleLidSwitch=ignore/g' /etc/systemd/logind.conf
    sed --in-place 's/^[#]HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/g' /etc/systemd/logind.conf
    sed --in-place 's/^[#]HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/g' /etc/systemd/logind.conf
}

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

# Install openssh-server only if the IS_INTEGRATION_TEST variable is enable
if  [ "$IS_INTEGRATION_TEST" == "true" ]; then
    common_pkgs=("${common_pkgs[@]}" "openssh-server")
fi

if    [ "$CODENAME" == "bionic" ]; then
  apt_pkg_list=("${pkgs_specific_to_ubuntu1804_bionic_32bit[@]}" "${common_pkgs[@]}")
elif  [ "$CODENAME" == "bookworm" ]; then
  apt_pkg_list=("${pkgs_specific_to_debian_bookworm[@]}" "${common_pkgs[@]}" "openssh-server")
elif  [ "$CODENAME" == "focal" ]; then
  apt_pkg_list=("${pkgs_specific_to_ubuntu2004_focal[@]}" "${common_pkgs[@]}")
elif  [ "$CODENAME" == "jammy" ]; then
  apt_pkg_list=("${pkgs_specific_to_ubuntu2204_jammy[@]}" "${common_pkgs[@]}")
elif  [ "$CODENAME" == "oracular" ]; then
  apt_pkg_list=("${pkgs_specific_to_ubuntu2410_oracular[@]}" "${common_pkgs[@]}")
elif  [ "$CODENAME" == "noble" ]; then
  apt_pkg_list=("${pkgs_specific_to_ubuntu2404_noble[@]}" "${common_pkgs[@]}")
else
  echo "Warning: Unknown release codename $CODENAME"
  exit 1
fi

apt-get install --yes --no-install-recommends -o Dpkg::Options::="--force-confnew" "${apt_pkg_list[@]}"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to install packages."
    exit 1
fi

if  [ "$CODENAME" == "bionic" ]; then
  # Ensure the Python3 symlink points to Python 3.7 on Ubuntu 18.04 Bionic, as it uses Python 3.6 by default
  # and Rescuezilla relies on a few Python 3.7 features, such as subprocess module's capture_output parameter
  update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.7 1
  # HACK: Ensure Python GObject Introspection library doesn't fail using Python 3. [1]
  # [1] https://stackoverflow.com/a/62672285/4745097
  ln -s /usr/lib/python3/dist-packages/gi/_gi.cpython-{36m,37m}-i386-linux-gnu.so
  # HACK: Similar issue with python-apt and python 3.7 [1]
  # [1] https://stackoverflow.com/a/57147858/4745097
  ln -s /usr/lib/python3/dist-packages/apt_pkg.cpython-{36m,37m}-${ARCH}-linux-gnu.so
  ln -s /usr/lib/python3/dist-packages/apt_inst.cpython-{36m,37m}-${ARCH}-linux-gnu.so
fi

if  [ "$IS_INTEGRATION_TEST" == "true" ]; then
    bash /install-linux-query-tcp-server.sh
fi

# Lowers systemd timeout if a service cannot start, as a 90 second delay in boot/shutdown
# provides a very poor user experience.
sed --in-place 's/#DefaultTimeoutStartSec=90s/DefaultTimeoutStartSec=10s/g' /etc/systemd/system.conf
sed --in-place 's/#DefaultTimeoutStopSec=90s/DefaultTimeoutStopSec=10s/g' /etc/systemd/system.conf

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

update_logind_conf_to_ignore_laptop_lid_switch

# Prevent GParted from launching if there is an instance of Rescuezilla running.
#
cat << EOF > /tmp/gparted.rescuezilla.check.sh
#!/bin/sh
#
# Cannot launch GParted if Rescuezilla is running.
#
if test "z\`ps -e | grep rescuezillapy\`" != "z"; then
        MESSAGE="Cannot launch GParted because the process rescuezillapy is running.\n\nClose Rescuezilla then try again."
        printf "\$MESSAGE"
        yad --center --width 300 --title="\$TITLE." --button="OK:0" --text "\$MESSAGE"
        exit 1
fi
EOF
cp /usr/sbin/gparted /usr/sbin/gparted.copy
# Remove #!/bin/sh shebang from the GParted launcher script
sed --in-place '1d' /usr/sbin/gparted.copy
# Prepend the Rescuezilla check to the GParted launcher script.
cat /tmp/gparted.rescuezilla.check.sh /usr/sbin/gparted.copy > /usr/sbin/gparted
rm /usr/sbin/gparted.copy

ln -s /usr/bin/pcmanfm /usr/bin/nautilus
rm /usr/bin/{rpcclient,smbcacls,smbclient,smbcquotas,smbget,smbspool,smbtar}
rm /usr/share/icons/*/icon-theme.cache
rm -rf /usr/share/doc
rm -rf /usr/share/man
rm -rf /etc/network/if-up.d/ntpdate
