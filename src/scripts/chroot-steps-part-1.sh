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

# Packages specific to Rescuezilla 32-bit build (currently based Ubuntu 18.04 Bionic)
# Hardware Enablement (HWE, also called LTS Enablement Stack) [1] [2]
# https://wiki.ubuntu.com/Kernel/LTSEnablementStack
# https://ubuntu.com/about/release-cycle
pkgs_specific_to_ubuntu1804_bionic_32bit=("linux-generic-hwe-18.04"
                        "xserver-xorg-hwe-18.04"
                        "xserver-xorg-video-all-hwe-18.04"
                        "xserver-xorg-video-intel-hwe-18.04"
                        "xserver-xorg-video-qxl-hwe-18.04"
                        # Python3.7 as Rescuezilla uses subprocess's "capture_output" parameter
                        "python3.7"
                        # Explicitly install dmidecode as it appears to have been pulled in on other distros by a dependency
                        "dmidecode"
                        # Add support for crypto volumes mount (luks, bitlocker, crypt)
                        "libblockdev-crypto2"
                        "ibus-anthy"
                        "reiser4progs"
                        "python3-whichcraft"
)

# Packages specific to Rescuezilla 64-bit build (currently based Ubuntu 20.04 Focal)
# TODO: Switch to Hardware Enablement (HWE, also called LTS Enablement Stack) [1] [2]
#       when it is released.
# https://wiki.ubuntu.com/Kernel/LTSEnablementStack
# https://ubuntu.com/about/release-cycle
pkgs_specific_to_ubuntu2004_focal=("linux-generic-hwe-18.04"
                       "xserver-xorg-hwe-18.04"
                       "xserver-xorg-video-all-hwe-18.04"
                       "xserver-xorg-video-intel-hwe-18.04"
                       "xserver-xorg-video-qxl-hwe-18.04"
                       # Packages which may assist users needing to do a GRUB repair (64-bit EFI)
                       "shim-signed"
                       "grub-efi-amd64-signed"
                       "grub-efi-amd64-bin"
                       "grub-efi-ia32-bin"
                       # Dependency for Rescuezilla Image Explorer
                       "nbdkit"
                       "lupin-casper"
                       # Replaced by exfatprogs
                       "exfat-utils"
                       # Removed since 22.10 Kinetic
                       "plymouth-theme-ubuntu-logo"
                       # Add support for crypto volumes mount (luks, bitlocker, crypt)
                       "libblockdev-crypto2"
                       "ibus-anthy"
                       "reiser4progs"
                       "python3-whichcraft"
)

pkgs_specific_to_ubuntu2204_jammy=(
                       "linux-generic"
                       "xserver-xorg"
                       "xserver-xorg-video-all"
                       "xserver-xorg-video-intel"
                       "xserver-xorg-video-qxl"
                       "xserver-xorg-video-mga"
                        # Packages which may assist users needing to do a GRUB repair (64-bit EFI)
                       "shim-signed"
                       "grub-efi-amd64-signed"
                       "grub-efi-amd64-bin"
                       "grub-efi-ia32-bin"
                       # Dependency for Rescuezilla Image Explorer
                       "nbdkit"
                       # Replaces exfat-utils
                       "exfatprogs"
                       # Removed since 22.10 Kinetic
                       "plymouth-theme-ubuntu-logo"
                       # Add support for crypto volumes mount (luks, bitlocker, crypt)
                       "libblockdev-crypto2"
                       "ibus-anthy"
                       "reiser4progs"
                       "python3-whichcraft"
)

pkgs_specific_to_ubuntu2410_oracular=(
                       "linux-generic"
                       "xserver-xorg"
                       "xserver-xorg-video-all"
                       "xserver-xorg-video-intel"
                       "xserver-xorg-video-qxl"
                       "xserver-xorg-video-mga"
                        # Packages which may assist users needing to do a GRUB repair (64-bit EFI)
                       "shim-signed"
                       "grub-efi-amd64-signed"
                       "grub-efi-amd64-bin"
                       "grub-efi-ia32-bin"
                       # Dependency for Rescuezilla Image Explorer
                       "nbdkit"
                       # Replaces exfat-utils
                       "exfatprogs"
                       # Add support for crypto volumes mount (luks, bitlocker, crypt)
                       "libblockdev-crypto3"
                       # "Legacy "local authority" (.pkla) backend for polkitd" required so polkit works on Mantic
                       "polkitd-pkla"
                       "ibus-anthy"
)

pkgs_specific_to_ubuntu2404_noble=(
                       "linux-generic"
                       "xserver-xorg"
                       "xserver-xorg-video-all"
                       "xserver-xorg-video-intel"
                       "xserver-xorg-video-qxl"
                       "xserver-xorg-video-mga"
                        # Packages which may assist users needing to do a GRUB repair (64-bit EFI)
                       "shim-signed"
                       "grub-efi-amd64-signed"
                       "grub-efi-amd64-bin"
                       "grub-efi-ia32-bin"
                       # Dependency for Rescuezilla Image Explorer
                       "nbdkit"
                       # Replaces exfat-utils
                       "exfatprogs"
                       # Add support for crypto volumes mount (luks, bitlocker, crypt)
                       "libblockdev-crypto3"
                       # "Legacy "local authority" (.pkla) backend for polkitd" required so polkit works on Mantic
                       "polkitd-pkla"
                       "reiser4progs"
                       "python3-whichcraft"
)

# Languages on the system
lang_codes=(
             "ar"
             "ca"
             "cs"
             "da"
             "de"
             "el"
             "es"
             "fa"
             "fi"
             "fr"
             "ko"
             "id"
             "it"
             "he"
             "lt"
             "hu"
             "nl"
             "ja"
             "nb"
             "pl"
             "pt"
             "ro"
             "ru"
             "sk"
             "sq"
             "sv"
             "th"
             "tr"
             "uk"
             "vi"
             "zh-hans"
             "zh-hant"
)

# Prepare list of language packs to install
language_pack_gnome_base_pkgs=()
firefox_locale_pkgs=()
for lang in "${lang_codes[@]}"
do
     firefox_locale_pkgs+=("firefox-locale-$lang")
     language_pack_gnome_base_pkg+=("language-pack-gnome-$lang-base")
done

# Packages common to both  32-bit and 64-bit build
# TODO: Documentation each package with why these particular packages are present,
# TODO: and what they do.
common_pkgs=("discover"
             "laptop-detect"
             "casper"
             "openbox"
             "lightdm"
             # Firmware package for NVidia cards from ~2009 (newer cards have firmware in the kernel)
             "nouveau-firmware"
             "x11-xserver-utils"
             "xterm"
             "network-manager-gnome"
             "plymouth-x11"
             "plymouth-label"
             "pcmanfm"
             # PCManFM recommended packages to resolve paths like eg, smb://fileserver/johnsmith
             # TODO: Re-enable GVFS packages -- seems to cause issues around preventing refreshing partition
             # tables due to  busy disks. See Rescuezilla launch script for more information.
             #"gvfs-backends"
             #"gvfs-fuse"
             "firefox"
             "${firefox_locale_pkgs[@]}"
              # Japanese font
             "fonts-takao-mincho"
             # Chinese font
             "fonts-wqy-zenhei"
             # Korean font
             "fonts-unfonts-core"
             # Thai font
             "fonts-thai-tlwg"
             # Font for symbols like "❌"
             "fonts-symbola"
             "breeze-gtk-theme"
             "gnome-icon-theme"
             "gnome-brave-icon-theme"
             "dmz-cursor-theme"
             "gpicview"
             "mousepad"
             "lxmenu-data"
             "arandr"
             "xfce4-terminal"
             "lxpanel"
             "fonts-ubuntu"
             "alsamixergui"
             "volumeicon-alsa"
             "pm-utils"
             "notify-osd"
             "notify-osd-icons"
             "time"
             "psmisc"
             "openssh-client"
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
             "mdadm"
             "lshw-gtk"
             "ecryptfs-utils"
             "partimage"
             "clonezilla"
             "testdisk"
             "gddrescue"
             "usb-creator-gtk"
             "wodim"
             # CLI tool to install *.deb files while resolving dependencies
             "gdebi-core"
             "cryptsetup"
             "reiserfsprogs"
             "dosfstools"
             "mtools"
             "ntfs-3g"
             "hfsutils"
             "jfsutils"
             "wget"
             "exfat-fuse"
             "btrfs-progs"
             "udisks2-btrfs"
             # Add support to ext4/f2fs kernel FBE
             "fscrypt"
             "libpam-fscrypt"
             "hfsplus"
             "hfsprogs"
             "f2fs-tools"
             "lvm2"
             "xfsdump"
             "xfsprogs"
             "udftools"
             "grub-pc-bin"
             "grub2-common"
             "${language_pack_gnome_base_pkg[@]}"
             "qemu-utils"
             "xfce4-screenshooter"
             "wpasupplicant"
             "lxappearance"
             "flashrom"
             "hashdeep"
)

# Install openssh-server only if the IS_INTEGRATION_TEST variable is enable
if  [ "$IS_INTEGRATION_TEST" == "true" ]; then
    common_pkgs=("${common_pkgs[@]}" "openssh-server")
fi

if    [ "$CODENAME" == "bionic" ]; then
  apt_pkg_list=("${pkgs_specific_to_ubuntu1804_bionic_32bit[@]}" "${common_pkgs[@]}")
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

apt-get install --yes --no-install-recommends "${apt_pkg_list[@]}"
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
