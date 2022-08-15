#!/bin/bash

# Echo each command
set -x

# Flag to enable integration test mode [1]. Disabled by default.
#
# Images built with this flag include an SSH server, a simple netcat TCP query server,
# and other changes to support Rescuezilla's automated end-to-end integration test suite [1].
#
# The flag is very useful for development and debugging too.  The SSH server is handy, as is
# the lower compression ratio on the squashfs root filesystem (for faster builds during development).
#
# This flag is obviously never enabled in production builds, and users are able to easily
# audit that no SSH server or netcat TCP query server is ever installed.
#
# [1] See src/integration-test/README.md for more information.
#
IS_INTEGRATION_TEST="${IS_INTEGRATION_TEST=:false}"

# Set the default base operating system, using the Ubuntu release's shortened code name [1].
# [1] https://wiki.ubuntu.com/Releases
CODENAME="${CODENAME:-INVALID}"

# Sets CPU architecture using Ubuntu designation [1]
# [1] https://help.ubuntu.com/lts/installation-guide/armhf/ch02s01.html
ARCH="${ARCH:-INVALID}"

# Directory containing this build script
BASEDIR=$(dirname $(readlink -f "$0"))

RESCUEZILLA_ISO_FILENAME=rescuezilla.$ARCH.$CODENAME.iso
# The base build directory is "build/", unless overridden by an environment variable
BASE_BUILD_DIRECTORY=${BASE_BUILD_DIRECTORY:-build/${BASE_BUILD_DIRECTORY}}
BUILD_DIRECTORY=${BUILD_DIRECTORY:-${BASE_BUILD_DIRECTORY}/${CODENAME}.${ARCH}}
mkdir -p "$BUILD_DIRECTORY/chroot"
# Ensure the build directory is an absolute path
BUILD_DIRECTORY=$( readlink -f "$BUILD_DIRECTORY" )
PKG_CACHE_DIRECTORY=${PKG_CACHE_DIRECTORY:-pkg.cache}
# Use a recent version of debootstrap from git
DEBOOTSTRAP_SCRIPT_DIRECTORY=${BASEDIR}/src/third-party/debootstrap
DEBOOTSTRAP_CACHE_DIRECTORY=debootstrap.$CODENAME.$ARCH
APT_PKG_CACHE_DIRECTORY=var.cache.apt.archives.$CODENAME.$ARCH
APT_INDEX_CACHE_DIRECTORY=var.lib.apt.lists.$CODENAME.$ARCH

# If the current commit is not tagged, the version number from `git
# describe--tags` is X.Y.Z-abc-gGITSHA-dirty, where X.Y.Z is the previous tag,
# 'abc' is the number of commits since that tag, gGITSHA is the git sha
# prepended by a 'g', and -dirty is present if the working tree has been
# modified.
#
# Note: the --match is a glob, not a regex.
VERSION_STRING=$(git describe --tags --match="[0-9].[0-9]*" --dirty)

# Date of current git commit in colon-less ISO 8601 format (2013-04-01T130102)
GIT_COMMIT_DATE=$(date +"%Y-%m-%dT%H%M%S" --date=@$(git show --no-patch --format=%ct HEAD))

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please consult build instructions." 
   exit 1
fi

if [ "$CODENAME" = "INVALID" ] || [ "$ARCH" = "INVALID" ]; then
  echo "The variable CODENAME=${CODENAME} or ARCH=${ARCH} was not set correctly. Are you using the Makefile? Please consult build instructions."
  exit 1
fi

# debootstrap part 1/2: If package cache doesn't exist, download the packages
# used in a base Debian system into the package cache directory [1]
#
# [1] https://unix.stackexchange.com/a/397966
if [ ! -d "$PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY" ] ; then
    mkdir -p $PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY
    # Selecting a geographically closer APT mirror may increase network transfer rates.
    #
    # Note: After the support window for a specific release ends, the packages are moved to the 'old-releases' 
    # URL [1], which means substitution becomes mandatory in-order to build older releases from scratch.
    #
    # [1] http://old-releases.ubuntu.com/ubuntu
    TARGET_FOLDER=`readlink -f $PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY`
    pushd ${DEBOOTSTRAP_SCRIPT_DIRECTORY}
    DEBOOTSTRAP_DIR=${DEBOOTSTRAP_SCRIPT_DIRECTORY} ./debootstrap --arch=$ARCH --foreign $CODENAME $TARGET_FOLDER http://archive.ubuntu.com/ubuntu/
    RET=$?
    popd
    if [[ $RET -ne 0 ]]; then
        echo "debootstrap part 1/2 failed. This may occur if you're using an older version of deboostrap"
        echo "that doesn't have a script for \"$CODENAME\". Please consult the build instructions." 
        exit 1
    fi
fi

echo "Copy debootstrap package cache"
rsync --archive "$PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY/" "$BUILD_DIRECTORY/chroot/"
RET=$?
if [[ $RET -ne 0 ]]; then
    echo "Failed to copy"
    exit 1
fi
 
# debootstrap part 2/2: Bootstrap a Debian root filesystem based on cached packages directory (part 2/2)
chroot $BUILD_DIRECTORY/chroot/ /bin/bash -c 'DEBOOTSTRAP_DIR="debootstrap" ./debootstrap/debootstrap --second-stage'
RET=$?
if [[ $RET -ne 0 ]]; then
    echo "debootstrap part 2/2 failed. This may occur if the package cache ($PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY/)"
    echo "exists but is not fully populated. If so, deleting this directory might help. Please consult the build instructions." 
    exit 1
fi

# Ensures tmp directory has correct mode, including sticky-bit
chmod 1777 "$BUILD_DIRECTORY/chroot/tmp/"

# Copy cached apt packages, if present, to reduce need to download packages from internet
if [ -d "$PKG_CACHE_DIRECTORY/$APT_PKG_CACHE_DIRECTORY/" ] ; then
    mkdir -p "$BUILD_DIRECTORY/chroot/var/cache/apt/archives/"
    echo "Copy apt package cache"
    rsync --archive "$PKG_CACHE_DIRECTORY/$APT_PKG_CACHE_DIRECTORY/" "$BUILD_DIRECTORY/chroot/var/cache/apt/archives"
    RET=$?
    if [[ $RET -ne 0 ]]; then
        echo "Failed to copy"
        exit 1
    fi
fi

# Copy cached apt indexes, if present, to a temporary directory, to reduce need to download packages from internet.
if [ -d "$PKG_CACHE_DIRECTORY/$APT_INDEX_CACHE_DIRECTORY/" ] ; then
    mkdir -p "$BUILD_DIRECTORY/chroot/var/lib/apt/"
    echo "Copy apt index cache"
    rsync --archive "$PKG_CACHE_DIRECTORY/$APT_INDEX_CACHE_DIRECTORY/" "$BUILD_DIRECTORY/chroot/var/lib/apt/lists.cache"
    RET=$?
    if [[ $RET -ne 0 ]]; then
        echo "Failed to copy"
        exit 1
    fi
fi

cd "$BUILD_DIRECTORY"
# Enter chroot, and launch next stage of script
mount --bind /dev chroot/dev

# Copy files related to network connectivity
cp /etc/hosts chroot/etc/hosts
cp /etc/resolv.conf chroot/etc/resolv.conf

# Copy the CHANGELOG
rsync --archive "$BASEDIR/CHANGELOG" "$BUILD_DIRECTORY/chroot/usr/share/rescuezilla/"
RET=$?
if [[ $RET -ne 0 ]]; then
    echo "Failed to copy"
    exit 1
fi

# Synchronize apt package manager configuration files
rsync --archive "$BASEDIR/src/livecd/chroot/etc/apt/" "$BUILD_DIRECTORY/chroot/etc/apt"
RET=$?
if [[ $RET -ne 0 ]]; then
    echo "Failed to copy"
    exit 1
fi

if  [ "$IS_INTEGRATION_TEST" == "true" ]; then
    LINUX_QUERY_SERVER_INSTALLER="$BASEDIR/src/integration-test/scripts/install_linux_query_tcp_server.sh"
    rsync --archive "$LINUX_QUERY_SERVER_INSTALLER" "$BUILD_DIRECTORY/chroot/"
    RET=$?
    if [[ $RET -ne 0 ]]; then
        echo "Failed to copy"
        exit 1
    fi
fi

# Renames the apt-preferences file to ensure backports and proposed
# repositories for the desired code name are never automatically selected.
pushd "chroot/etc/apt/preferences.d/"
mv "89_CODENAME_SUBSTITUTE-backports_default" "89_$CODENAME-backports_default"
mv "90_CODENAME_SUBSTITUTE-proposed_default" "90_$CODENAME-proposed_default"
popd

mv "chroot/etc/apt/sources.list.d/mozillateam-ubuntu-ppa-CODENAME_SUBSTITUTE.list" "chroot/etc/apt/sources.list.d/mozillateam-ubuntu-ppa-$CODENAME.list"

pushd "chroot/etc/apt/sources.list.d/"
# Since Ubuntu 22.04 (Jammy) firefox packaged as snap, which is not easily installed in a chroot
# [1] https://bugs.launchpad.net/snappy/+bug/1609903
mv "mozillateam-ubuntu-ppa-CODENAME_SUBSTITUTE.list" "mozillateam-ubuntu-ppa-CODENAME_SUBSTITUTE.list"
popd
APT_CONFIG_FILES=(
    "chroot/etc/apt/preferences.d/89_$CODENAME-backports_default"
    "chroot/etc/apt/preferences.d/90_$CODENAME-proposed_default"
    "chroot/etc/apt/sources.list.d/mozillateam-ubuntu-ppa-$CODENAME.list"
    "chroot/etc/apt/sources.list"
)
# Substitute Ubuntu code name into relevant apt configuration files
for apt_config_file in "${APT_CONFIG_FILES[@]}"; do
  sed --in-place s/CODENAME_SUBSTITUTE/$CODENAME/g $apt_config_file
done

cp "$BASEDIR/chroot.steps.part.1.sh" "$BASEDIR/chroot.steps.part.2.sh" chroot
# Launch first stage chroot. In other words, run commands within the root filesystem
# that is being constructed using binaries from within that root filesystem.
chroot chroot/ /bin/bash -c "IS_INTEGRATION_TEST=$IS_INTEGRATION_TEST ARCH=$ARCH CODENAME=$CODENAME /chroot.steps.part.1.sh"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to execute chroot steps part 1."
    exit 1
fi

rm "$BUILD_DIRECTORY/chroot/install_linux_query_tcp_server.sh"

cd "$BASEDIR"
# Copy the source FHS filesystem tree onto the build's chroot FHS tree, overwriting the base files where conflicts occur.
# The only exception the apt package manager configuration files which have already been copied above.
rsync --archive --exclude "chroot/etc/apt" src/livecd/ "$BUILD_DIRECTORY"
RET=$?
if [[ $RET -ne 0 ]]; then
    echo "Failed to copy"
    exit 1
fi

cp --archive $BUILD_DIRECTORY/../*.deb "$BUILD_DIRECTORY/chroot/"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy Rescuezilla deb packages."
    exit 1
fi
# Create desktop icon shortcuts
ln -s /usr/share/applications/rescuezilla.desktop "$BUILD_DIRECTORY/chroot/home/ubuntu/Desktop/rescuezilla.desktop"
ln -s /usr/share/applications/org.xfce.mousepad.desktop "$BUILD_DIRECTORY/chroot/home/ubuntu/Desktop/mousepad.desktop"
ln -s /usr/share/applications/gparted.desktop "$BUILD_DIRECTORY/chroot/home/ubuntu/Desktop/gparted.desktop"

# Process GRUB locale files
pushd "$BUILD_DIRECTORY/image/boot/grub/locale/"
for grub_po_file in *.po; do
        if [[ ! -f "$grub_po_file" ]]; then
                echo "Warning: $grub_po_file translation does not exist. Skipping."
        else
                # Remove .po extension from filename
                lang=$(echo "$grub_po_file" | cut -f 1 -d '.')
                echo "Converting language translation file: $BUILD_DIRECTORY/image/boot/grub/locale/$grub_po_file to $lang.mo" 
                msgfmt --output-file="$lang.mo" "$grub_po_file"
                if [[ $? -ne 0 ]]; then
                        echo "Error: Unable to convert GRUB bootloader configuration $lang translation from text-based po format to binary mo format."
                        exit 1
                fi
                # Remove unused *.po file
                rm "$grub_po_file"
        fi
done
popd

# Most end-users will not understand the terms i386 and AMD64.
MEMORY_BUS_WIDTH=""
if  [ "$ARCH" == "i386" ]; then
  MEMORY_BUS_WIDTH="32bit"
elif  [ "$ARCH" == "amd64" ]; then
  MEMORY_BUS_WIDTH="64bit"
else
    echo "Warning: unknown register width $ARCH"
fi

SUBSTITUTIONS=(
    # GRUB boot menu 
    "$BUILD_DIRECTORY/image/boot/grub/theme/theme.txt"
    # Firefox browser homepage query-string, to be able to provide a "You are using an old version. Please update."
    # message when users open the web browser with a (inevitably) decades old version.
    "$BUILD_DIRECTORY/chroot/usr/lib/firefox/distribution/policies.json"
)
for file in "${SUBSTITUTIONS[@]}"; do
    # Substitute version into file
    sed --in-place s/VERSION-SUBSTITUTED-BY-BUILD-SCRIPT/${VERSION_STRING}/g $file
    # Substitute CPU architecture description into file
    sed --in-place s/ARCH-SUBSTITUTED-BY-BUILD-SCRIPT/${ARCH}/g $file
    # Substitute CPU human-readable CPU architecture into file
    sed --in-place s/MEMORY-BUS-WIDTH-SUBSTITUTED-BY-BUILD-SCRIPT/${MEMORY_BUS_WIDTH}/g $file
    # Substitute date
    sed --in-place s/GIT-COMMIT-DATE-SUBSTITUTED-BY-BUILD-SCRIPT/${GIT_COMMIT_DATE}/g $file
done

# Enter chroot again
cd "$BUILD_DIRECTORY"
chroot chroot/ /bin/bash /chroot.steps.part.2.sh
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to execute chroot steps part 2."
    exit 1
fi

rsync --archive chroot/var.cache.apt.archives/ "$BASEDIR/$PKG_CACHE_DIRECTORY/$APT_PKG_CACHE_DIRECTORY"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy."
    exit 1
fi

rm -rf chroot/var.cache.apt.archives
rsync --archive chroot/var.lib.apt.lists/ "$BASEDIR/$PKG_CACHE_DIRECTORY/$APT_INDEX_CACHE_DIRECTORY"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy."
    exit 1
fi
rm -rf chroot/var.lib.apt.lists

umount -lf chroot/dev/
rm chroot/root/.bash_history
rm chroot/chroot.steps.part.1.sh chroot/chroot.steps.part.2.sh

mkdir -p image/casper image/memtest
cp chroot/boot/vmlinuz-*-generic image/casper/vmlinuz
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy vmlinuz image."
    exit 1
fi
# Ensures compressed Linux kernel image is readable during the MD5 checksum at boot
chmod 644 image/casper/vmlinuz

cp chroot/boot/initrd.img-*-generic image/casper/initrd.lz
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy initrd image."
    exit 1
fi

cp /boot/memtest86+.bin image/memtest/
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy memtest86+ binary from host system."
    exit 1
fi

# Create manifest
chroot chroot dpkg-query -W --showformat='${Package} ${Version}\n' > image/casper/filesystem.manifest
cp -v image/casper/filesystem.manifest image/casper/filesystem.manifest-desktop
REMOVE=("ubiquity"
        "ubiquity-frontend-gtk"
        "ubiquity-frontend-kde"
        "casper"
        "live-initramfs"
        "user-setup"
        "discover"
        "xresprobe"
        "os-prober"
        "libdebian-installer4"
)
for remove in "${REMOVE[@]}"
do
     sed -i "/${remove}/d" image/casper/filesystem.manifest-desktop
done

cat << EOF > image/README.diskdefines
#define DISKNAME Rescuezilla
#define TYPE binary
#define TYPEbinary 1
#define ARCH $ARCH
#define ARCH$ARCH 1
#define DISKNUM 1
#define DISKNUM1 1
#define TOTALNUM 0
#define TOTALNUM0 1
EOF

touch image/ubuntu
mkdir image/.disk
cd image/.disk
touch base_installable
echo "full_cd/single" > cd_type
echo "Ubuntu Remix" > info
echo "https://rescuezilla.com" > release_notes_url
cd ../..

rm -rf image/casper/filesystem.squashfs "$RESCUEZILLA_ISO_FILENAME"

echo "Compressing squashfs using zstandard (rather than default gzip)."
if  [ "$IS_INTEGRATION_TEST" == "true" ]; then
    echo "Using lowest possible compression level of 1 to speed up compression for debug builds." 
    COMPRESSION_LEVEL=1
else
    echo "Using max compression level of 19. The compression time is greatly increased, but the decompression time "
    echo "is the same as gzip (though uses more memory). The benefit is the compression ratio is improved over gzip."
    COMPRESSION_LEVEL=19
fi

mksquashfs chroot image/casper/filesystem.squashfs -comp zstd -b 1M -Xcompression-level "${COMPRESSION_LEVEL}" -e boot -e /sys
printf $(sudo du -sx --block-size=1 chroot | cut -f1) > image/casper/filesystem.size
cd image

# Create unpacked EFI directory
mkdir --parents "$BUILD_DIRECTORY/image/EFI/BOOT/"
# Add the Microsoft-signed EFI Secure Boot shim for AMD64 to the EFI System Partition (ESP). Also renames the shim to be the default bootloader
# so is automatically launched when the UEFI firmware launches this device. Given the target Linux kernel is Canonical-signed, for Secure Boot
# to work the shim needs to be from Ubuntu's `shim-signed` package (which trusts Canonical keys), see below.
cp /usr/lib/shim/shimx64.efi.signed "$BUILD_DIRECTORY/image/EFI/BOOT/BOOTx64.EFI"
# Add the Canonical-signed GRUB EFI loader executable for AMD64 to the ESP. This is a small EFI executable which is launched by the shim. It reads
# the nearby grub.cfg and uses it to access the squashfs-compressed filesystem to read another grub.cfg access other GRUB modules etc.
#
# Given the target Linux kernel is Canonical-signed, for Secure Boot to work the shim needs to be from Ubuntu's `grub-efi-amd64-signed package`
# (which trusts Canonical keys), it will not verify with Debian's `grub-efi-amd64-signed` package (as it trusts Debian's keys, so cannot verify
# a Canonical-signed kernel)
cp /usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed "$BUILD_DIRECTORY/image/EFI/BOOT/grubx64.efi"
# Deploy the GRUB AMD64 support files, including loadable modules
cp -r /usr/lib/grub/x86_64-efi "$BUILD_DIRECTORY/image/boot/grub/"

mkdir "$BUILD_DIRECTORY/image/boot/grub/fonts"
# Deploy unicode font
cp /usr/share/grub/unicode.pf2 "$BUILD_DIRECTORY/image/boot/grub/fonts"

# Copy the GRUB EFI loader executable for i386 (there is no signed GRUB EFI versions available for i386). Multiple EFI bootloaders for different
# CPU architectures can safely co-exist (given the different filenames), with the EFI firmware launching the correctly named executable.
# Also, Bay Trail Intel Atom CPUs apparently have 64-bit CPUs with 32-bit UEFI, so having both i386 and amd64 executable on an amd64 ISO seems good.
cp /usr/lib/grub/i386-efi/monolithic/grubia32.efi "$BUILD_DIRECTORY/image/EFI/BOOT/BOOTIA32.EFI"
# Deploy i386 GRUB EFI support files, including loadable modules
cp -r /usr/lib/grub/i386-efi "$BUILD_DIRECTORY/image/boot/grub/"
# Deploy i386 GRUB non-EFI support files to support El Torito optical disk boot on both i386 and amd64 systems using either ISO architecture variant
cp -r /usr/lib/grub/i386-pc "$BUILD_DIRECTORY/image/boot/grub/"

# Create an EFI System Partition (ESP), by first creating a small blank file then formatting a file as a FAT16 filesystem.
#
# Background: The UEFI firmware on a computer accesses the EFI System Partition, which is a small partition, which is immediately
# after the MBR (on non-removable drives) and launches an executable bootloader (in this case GRUB), which contains the filesystem drivers
# requires to to launch the next stage (in this case accessing the squashfs-compressed root filesystem to the display GRUB menu.
#
# More information on EFI bootloaders available in [1]
#
# [1] https://www.rodsbooks.com/efi-bootloaders/index.html
ESP_FAT_IMAGE="$BUILD_DIRECTORY/image/boot/esp.img"
rm "$ESP_FAT_IMAGE"
# Create an zeroed 6MiB file
dd if=/dev/zero of="$ESP_FAT_IMAGE" count=6 bs=1M
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to create blank file for EFI System Partition."
    exit 1
fi
# Creates a FAT16 filesystem, from the UEFI specification: "The EFI firmware must support the FAT32, FAT16, and FAT12 variants of the EFI
# file system. What variant of EFI FAT to use is defined by the size of the media." and "EFI encompasses the use of FAT32 for a system
# partition, and FAT12 or FAT16 for removable media." (from https://uefi.org/sites/default/files/resources/UEFI_Spec_2_8_final.pdf)
mkfs.msdos "$ESP_FAT_IMAGE"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to create MSDOS filesystem for EFI System Partition (ESP)."
    exit 1
fi

# Pack the EFI subdirectory in the "unpacked" EFI System Partition (ESP) temporary directory *into* [1] the FAT16 filesystem image to form the
# completed ESP (EFI System Partition) image.
# [1] See https://en.wikipedia.org/wiki/Mtools#Usage for more information.
mcopy -s -i "$ESP_FAT_IMAGE" "$BUILD_DIRECTORY/image/EFI" ::
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to pack EFI System Partition directory structure into FAT filesystem."
    exit 1
fi
# TODO: Delete the unpacked EFI/ directory. Currently it's still required because while EFI System Partition is correctly accessed and launched by
# all EFI firmware that has been tested, for some reason GRUB still tries to load (cd0)/EFI/ubuntu/grub.cfg from the ISO9660 filesystem, rather
# than loading the same file from the within the EFI system partition. Keeping the directory has no negative impact on the enduser except a
# few wasted megabytes.

# Generate the i386 CD-ROM/USB drive El Torito boot image (used for both AMD64/i386 CD-ROM boot) and save it in the ISO image filesystem
# TODO: Reduce number of GRUB modules to the absolute bare minimum.
grub-mkimage --format i386-pc-eltorito --output "$BUILD_DIRECTORY/image/boot/grub/grub.eltorito.bootstrap.img" --compression auto --prefix /boot/grub boot linux search normal configfile part_gpt fat iso9660 biosdisk test keystatus gfxmenu regexp probe efiemu all_video gfxterm font echo read ls cat png jpeg halt reboot part_msdos biosdisk
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to create the GRUB bootstrap image required for El Torito CD-ROM boot."
    exit 1
fi

# Pack the 'image' subdirectory to become a bootable ISO 9660 image using xorrisofs (which is "xorriso" but using the mkisofs/genisoimage
# compatibility mode).
#
# Constructing bootable ISO 9660 images is likely to be very esoteric knowledge for most developers reading this, so to better understand
# how it works, here is a quick reference/glossary:
#
# * ISO9660 is a filesystem commonly used on DVDs/CDs (though the filesystem UDF is also widely used on DVDs, and also used with Blu-Ray).
# * The goal here is to create a bootable ISO9660 image that works as a USB stick on legacy BIOS (MBR partition table), EFI (including Secure Boot),
#   and CD boot (El Torito boot catalog).
# * "EFI systems normally boot from optical discs by reading a FAT image file in El Torito format and treating that file as an ESP". This is in
#   contrast to the typical hard drive where the EFI partition resides on the disk rather than as an filesystem image file.
# * Historically, ISO9660 images were commonly created by mkisofs. mkisofs is no longer maintained. Debian repositories contain a fork of mkisofs named
#   genisoimage (forked in 2006), but it too is no longer developed (no bug fixes or features). Fortunately, xorriso is a command-line utility which is
#   maintained, widely available, and provides a compatibility mode for mkisofs' much clearer and higher-level command-line usage. While this
#   compatibility mode is accessible by launching xorriso with the "-as mkisofs" argument, the alternate executable xorrisofs achieves the same goal
#   more conveniently and with its own manpage.
# * The ISO9660 specification has had a number of extensions over the years. They are important to better understand xorrisofs command-line arguments:
#   * Rock Ridge added POSIX-style attributes (eg, ownership) and was developed in the early 1990s (named after a fictional town from a 1974 movie)
#   * Joliet reduced filename restrictions and was released by Microsoft in the mid-1990s
#   * El Torito is the CD-ROM boot record specification, which was released in 1995 (named after the restaurant it was supposedly defined in)
#   * An ISO 9660 filesystem can contain an MBR (Master Boot Record), ESP (EFI System Partition) and GPT (GUID Partition Table) without hampering the
#     (up-to 63) El Torito boot records. The MBR/GPT is stored in the first 32KiB of the filesystem. For developers familiar to hard drive layouts,
#     it may seem like a strange concept to have the MBR partition table stored within filesystem, rather than before the filesystem definition.
#
# Note: `man xorriso` is not at all relevant here. Instead, use `man xorrisofs` for more information on the arguments below. Also please note xorrisofs
#       specifies long-options sometimes with single-dash but other times with two dashes.
xorrisofs_args=(
               # Output image path
               --output "$BUILD_DIRECTORY/$RESCUEZILLA_ISO_FILENAME"
               # Set filesystem volume ID
               --volid "Rescuezilla"
               # "Enable Rock Ridge and set user and group id of all files in the ISO image to 0." (prevents files in the ISO image using uid/gid of
               # the user running the build. Also "Grant r-permissions to all. Deny all w-permissions. If any x-permission is set, grant x-permission to all.
               # Remove s-bit and t-bit". This does not affect the Linux root filesystem as it is squashfs-compressed so carries its own file attributes.
               -rational-rock
               # "Enable the production of an additional Joliet directory tree along with the ISO 9660 Rock Ridge tree".
               -joliet
               # "Allow up to 31 characters in ISO file names"
               -full-iso9660-filenames
               # Installs GRUB2 into the Master Boot Record (MBR) present within the ISO9660 "System Area", in order to support for disk boot
               # via legacy BIOS (eg, bootable USB sticks), while maintaining CD-ROM boot
               --grub2-mbr /usr/lib/grub/i386-pc/boot_hybrid.img
               # Specifies a boot image (using path relative to the ISO filesystem root) in the current entry of the El Torito catalog, and mark it
               # as bootable on legacy BIOS. This executable is 32-bit, but can load 64-bit systems.
               -eltorito-boot boot/grub/grub.eltorito.bootstrap.img
               # "Overwrite bytes 2548 to 2555 in the current boot image by the address" of the above boot image
               --grub2-boot-info
               # Don't emulate floppy disk when loading this El Torito boot image (to avoid requiring image exactly "1.2, 1.44or 2.88 Mb" in size)
               -no-emul-boot
               # Publishes El Torito boot catalog as datafile on the ISO. This file "is not significant for the booting PC-BIOS or EFI,
               # but it may later be read by other programs in order to learn about the available boot images"
               -eltorito-catalog boot/boot.cat
               # "Specifies the number of "virtual" (512-byte) sectors to load in no-emulation mode. The default is to load the entire boot file."
               -boot-load-size 4
               # Patches the legacy BIOS boot image (specified above with -b above) with a 56-byte "boot information table". This is supposedly
               # important for MBR legacy boot, and is used in examples across the internet. It populates the "Block address of the Primary Volume
               # Descriptor, block address of the boot image file, size of the boot image file"
               -boot-info-table
               # Specifies a boot image file (using path relative to the ISO filesystem root) to be mentioned in the current entry of the El Torito
               # boot catalog and mark suitable as EFI.  
               # Remember, "EFI systems normally boot from optical discs by reading a FAT image file and treating that file as an EFI System Partition"
               #
               # Please note, internally to xorrisofs this command first runs -eltorito-alt-boot (which finalizes the previously specified El Torito boot
               # catalog entry), then starts a second El Torito boot parameters set (up to 63 possible per ISO9660 filesystem), then specifies the
               # boot image file and marks it as suitable for EFI, then uses --no-emul-boot to stop floppy disk emulation (see above), then finalizes this
               # newly defined El Torito boot catalog entry.
               --efi-boot "boot/esp.img"
               # Exposes the EFI System Partition (ESP) image (specified above) in the GPT (GUID Partition Table) the ESP. In other words, exposes
               # the FAT partition that a computer's EFI firmware reads when booting from a USB stick (as opposed to the optical media case which boots
               # using EFI by reading the ESP from an image file)
               -efi-boot-part --efi-boot-image
               # Use contents of the specified directory as the ISO filesystem root
               "$BUILD_DIRECTORY/image/"
             )
# Create ISO image (part 1/4), with --boot-info-table argument modifying the El Torito boot image used for legacy BIOS booting (see comment above)
xorrisofs "${xorrisofs_args[@]}"

# Extract from the ISO image the El Torito boot image used for legacy BIOS booting, as it has been modified by --boot-info-table (part 2/4)
TEMP_MOUNT_DIR=$(mktemp --directory --suffix $RESCUEZILLA_ISO_FILENAME.temp.mount.dir)
mount "$BUILD_DIRECTORY/$RESCUEZILLA_ISO_FILENAME" "$TEMP_MOUNT_DIR"
cp "$TEMP_MOUNT_DIR/boot/grub/grub.eltorito.bootstrap.img" "$BUILD_DIRECTORY/image/boot/grub/grub.eltorito.bootstrap.img"
umount $TEMP_MOUNT_DIR
rmdir $TEMP_MOUNT_DIR

# Generate an md5sum of all files, including the MBR boot image now modified by --boot-info-table. (part 3/4)
find . -type f -print0 | xargs -0 md5sum | grep -v "./md5sum.txt" > md5sum.txt

# Create ISO image (part 4/4), the --boot-info-table modification already having been made to the MBR boot image, and md5sum capturing this correctly
xorrisofs "${xorrisofs_args[@]}"

cd "$BUILD_DIRECTORY"
mv "$BUILD_DIRECTORY/$RESCUEZILLA_ISO_FILENAME" ../

# TODO: Evaluate the "Errata" sections of the Redo Backup and Recovery
# TODO: Sourceforge Wiki, and determine if the build scripts need modification.
