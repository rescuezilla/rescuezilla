#!/bin/bash

# Echo each command
set -x

CODENAME=bionic
ARCH=i386
# The build directory is "build/", unless overridden by an environment variable
BUILD_DIRECTORY=${BUILD_DIRECTORY:-build}
PKG_CACHE_DIRECTORY=${PKG_CACHE_DIRECTORY:-pkg.cache}
DEBOOTSTRAP_CACHE_DIRECTORY=debootstrap.$CODENAME.$ARCH
APT_PKG_CACHE_DIRECTORY=var.cache.apt.archives.$CODENAME.$ARCH
APT_INDEX_CACHE_DIRECTORY=var.lib.apt.lists.$CODENAME.$ARCH

# If the current commit is not tagged, the version number from `git
# describe--tags` is X.Y.Z-abc-gGITSHA-dirty, where X.Y.Z is the previous tag,
# 'abc' is the number of commits since that tag, gGITSHA is the git sha
# prepended by a 'g', and -dirty is present if the working tree has been
# modified.
VERSION_STRING=$(git describe --tags --dirty)

# Date of current git commit in colon-less ISO 8601 format (2013-04-01T130102)
GIT_COMMIT_DATE=$(date +"%Y-%m-%dT%H%M%S" --date=@$(git show --no-patch --format=%ct HEAD))

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please consult build instructions." 
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
    debootstrap --arch=$ARCH --foreign $CODENAME $PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY http://archive.ubuntu.com/ubuntu/
    RET=$?
    if [[ $RET -ne 0 ]]; then
        echo "debootstrap part 1/2 failed. This may occur if you're using an older version of deboostrap"
        echo "that doesn't have a script for \"$CODENAME\". Please consult the build instructions." 
        exit 1
    fi
fi
mkdir -p $BUILD_DIRECTORY/chroot
echo "Copy debootstrap package cache"
rsync --archive $PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY/ $BUILD_DIRECTORY/chroot/

# debootstrap part 2/2: Bootstrap a Debian root filesystem based on cached
# packages directory (part 2/2) [1] Note DEBOOTSTRAP_DIR is an undocumented
# environment variable used by debootstrap according to [1].
#
# [1] https://unix.stackexchange.com/a/397966
DEBOOTSTRAP_DIR=$BUILD_DIRECTORY/chroot/debootstrap debootstrap --second-stage --second-stage-target $(readlink -f $BUILD_DIRECTORY/chroot/)
RET=$?
if [[ $RET -ne 0 ]]; then
    echo "debootstrap part 2/2 failed. This may occur if the package cache ($PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY/)"
    echo "exists but is not fully populated. If so, deleting this directory might help. Please consult the build instructions." 
    exit 1
fi

# Ensures tmp directory has correct mode, including sticky-bit
chmod 1777 $BUILD_DIRECTORY/chroot/tmp/

# Copy cached apt packages, if present, to reduce need to download packages from internet
if [ -d "$PKG_CACHE_DIRECTORY/$APT_PKG_CACHE_DIRECTORY/" ] ; then
    mkdir -p $BUILD_DIRECTORY/chroot/var/cache/apt/archives/
    echo "Copy apt package cache"
    rsync --archive $PKG_CACHE_DIRECTORY/$APT_PKG_CACHE_DIRECTORY/ $BUILD_DIRECTORY/chroot/var/cache/apt/archives
fi

# Copy cached apt indexes, if present, to a temporary directory, to reduce need to download packages from internet.
if [ -d "$PKG_CACHE_DIRECTORY/$APT_INDEX_CACHE_DIRECTORY/" ] ; then
    mkdir -p $BUILD_DIRECTORY/chroot/var/lib/apt/
    echo "Copy apt index cache"
    rsync --archive $PKG_CACHE_DIRECTORY/$APT_INDEX_CACHE_DIRECTORY/ $BUILD_DIRECTORY/chroot/var/lib/apt/lists.cache
fi

cd $BUILD_DIRECTORY
# Enter chroot, and launch next stage of script
mount --bind /dev chroot/dev
rsync --archive ../src/livecd/chroot/etc/apt/ chroot/etc/apt
cp /etc/hosts chroot/etc/hosts
cp /etc/resolv.conf chroot/etc/resolv.conf

cp ../chroot.steps.part.1.sh ../chroot.steps.part.2.sh chroot
chroot chroot/ /bin/bash /chroot.steps.part.1.sh
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to execute chroot steps part 1."
    exit 1
fi

# Copy the source FHS filesystem tree onto the build's chroot FHS tree, overwriting the base files where conflicts occur
cd ..
rsync --archive src/livecd/ $BUILD_DIRECTORY

LANG_CODES=(
    "fr"
    "de"
)
for lang in "${LANG_CODES[@]}"; do
    BASE="$BUILD_DIRECTORY/chroot/usr/share/locale/$lang/LC_MESSAGES/"
    pushd $BASE
    # Convert *.ko text-based GTK translations into *.mo.
    APP_NAMES=(
        "rescuezilla"
        "drivereset"
        "graphical-shutdown"
    )
    for app_name in "${APP_NAMES[@]}"; do
        if [[ ! -f "$app_name.ko" ]]; then
            echo "Warning: $BASE/$app_name.ko translation for $lang does not exist. Skipping."
        else
            msgfmt --output-file="$app_name.mo" "$app_name.ko"
            if [[ $? -ne 0 ]]; then
                echo "Error: Unable to convert $app_name's $lang translation from text-based ko format to binary mo format."
                exit 1
            fi
            # Remove unused *.ko file
            rm "$app_name.ko"
        fi
    done
    popd
done

SUBSTITUTIONS=(
    # Rescuezilla perl script
    "$BUILD_DIRECTORY/chroot/usr/share/rescuezilla/VERSION"
    "$BUILD_DIRECTORY/chroot/usr/share/rescuezilla/GIT_COMMIT_DATE"
    # ISOLINUX boot menu 
    "$BUILD_DIRECTORY/image/isolinux/isolinux.cfg"
    # Chromium browser homepage query-string, to be able to provide a "You are using an old version. Please update."
    # message when users open the web browser with a (inevitably) decades old version.
    "$BUILD_DIRECTORY/chroot/home/ubuntu/.config/chromium/Default/Preferences"
)
for file in "${SUBSTITUTIONS[@]}"; do
    # Substitute version into file
    sed --in-place s/VERSION-SUBSTITUTED-BY-BUILD-SCRIPT/${VERSION_STRING}/g $file
    # Substitute date
    sed --in-place s/GIT-COMMIT-DATE-SUBSTITUTED-BY-BUILD-SCRIPT/${GIT_COMMIT_DATE}/g $file
done

# Enter chroot again
cd $BUILD_DIRECTORY
chroot chroot/ /bin/bash /chroot.steps.part.2.sh
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to execute chroot steps part 2."
    exit 1
fi

rsync --archive chroot/var.cache.apt.archives/ ../$PKG_CACHE_DIRECTORY/$APT_PKG_CACHE_DIRECTORY
rm -rf chroot/var.cache.apt.archives
rsync --archive chroot/var.lib.apt.lists/ ../$PKG_CACHE_DIRECTORY/$APT_INDEX_CACHE_DIRECTORY
rm -rf chroot/var.lib.apt.lists

umount -lf chroot/dev/
rm chroot/root/.bash_history
rm chroot/chroot.steps.part.1.sh chroot/chroot.steps.part.2.sh

mkdir -p image/casper image/isolinux image/install
cp chroot/boot/vmlinuz-*-generic image/casper/vmlinuz
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy vmlinuz image."
    exit 1
fi

cp chroot/boot/initrd.img-*-generic image/casper/initrd.lz
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy initrd image."
    exit 1
fi

cp /usr/lib/syslinux/modules/bios/vesamenu.c32 \
   /usr/lib/ISOLINUX/isolinux.bin \
   /usr/lib/syslinux/modules/bios/ldlinux.c32 \
   /usr/lib/syslinux/modules/bios/libcom32.c32 \
   /usr/lib/syslinux/modules/bios/libutil.c32 \
   image/isolinux/
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy ISOLINUX files."
    exit 1
fi
cp /boot/memtest86+.bin image/install/memtest

# Create manifest
chroot chroot dpkg-query -W --showformat='${Package} ${Version}\n' > image/casper/filesystem.manifest
cp -v image/casper/filesystem.manifest image/casper/filesystem.manifest-desktop
REMOVE='ubiquity ubiquity-frontend-gtk ubiquity-frontend-kde casper lupin-casper live-initramfs user-setup discover xresprobe os-prober libdebian-installer4'
for i in $REMOVE; do
  sed -i "/${i}/d" image/casper/filesystem.manifest-desktop
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

rm -rf image/casper/filesystem.squashfs rescuezilla.iso
mksquashfs chroot image/casper/filesystem.squashfs -e boot -e /sys
printf $(sudo du -sx --block-size=1 chroot | cut -f1) > image/casper/filesystem.size
cd image
find . -type f -print0 | xargs -0 md5sum | grep -v "./md5sum.txt" > md5sum.txt

# Create ISO image (part 1/3), with -boot-info-table modifying isolinux.bin with 56-byte "boot information table" # at offset 8 in the file."
# See `man genisoimage` for more information. This modification invalidates the isolinux.bin md5sum calculated above.
genisoimage -r \
            -V "Rescuezilla" \
            -cache-inodes \
            -J \
            -l \
            -b isolinux/isolinux.bin \
            -c isolinux/boot.cat \
            -no-emul-boot \
            -boot-load-size 4 \
            -boot-info-table \
            -o ../rescuezilla.iso . 

# Generate fresh md5sum containing the -boot-info-table modified isolinux.bin
find . -type f -print0 | xargs -0 md5sum | grep -v "./md5sum.txt" > md5sum.txt
# Create ISO image (part 2/3), the --boot-info-table modification has already been made to isolinux.bin, so the md5sum remains correct this time.
rm ../rescuezilla.iso
genisoimage -r \
            -V "Rescuezilla" \
            -cache-inodes \
            -J \
            -l \
            -b isolinux/isolinux.bin \
            -c isolinux/boot.cat \
            -no-emul-boot \
            -boot-load-size 4 \
            -boot-info-table \
            -o ../rescuezilla.iso . 

cd ..

# Make ISO image USB bootable (part 3/3)
isohybrid rescuezilla.iso

# TODO: Evaluate the "Errata" sections of the Redo Backup and Recovery
# TODO: Sourceforge Wiki, and determine if the build scripts need modification.
