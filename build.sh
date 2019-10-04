#!/bin/bash

# Echo each command
set -x

# Selecting a geographically closer APT mirror may increase network transfer rates.
#
# Note: After the support window for a specific release ends, the packages are moved to the 'old-releases' 
# URL [1], which means substitution becomes mandatory in-order to build older releases from scratch.
#
# [1] http://old-releases.ubuntu.com/ubuntu
#
#APT_REPOSITORY_URL=http://archive.ubuntu.com/ubuntu
APT_REPOSITORY_URL=http://old-releases.ubuntu.com/ubuntu
CODENAME=precise
ARCH=i386
# The build directory is "build/", unless overridden by an environment variable
BUILD_DIRECTORY=${BUILD_DIRECTORY:-build}

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please consult build instructions." 
   exit 1
fi

# Prepare base system
mkdir -p $BUILD_DIRECTORY/chroot

cd $BUILD_DIRECTORY
debootstrap --arch=$ARCH $CODENAME chroot/ $APT_REPOSITORY_URL/

# Enter chroot, and launch next stage of script
mount --bind /dev chroot/dev
cp /etc/hosts chroot/etc/hosts
cp /etc/resolv.conf chroot/etc/resolv.conf
echo "deb $APT_REPOSITORY_URL $CODENAME main universe multiverse" > chroot/etc/apt/sources.list
cp ../chroot.steps.part.1.sh ../chroot.steps.part.2.sh chroot
chroot chroot/ /bin/bash /chroot.steps.part.1.sh

# Copy the source FHS filesystem tree onto the build's chroot FHS tree, overwriting the base files where conflicts occur
cd ..
rsync --archive --progress src/livecd/ $BUILD_DIRECTORY
cp src/adeskbar*.deb $BUILD_DIRECTORY/chroot/

# Enter chroot again
cd $BUILD_DIRECTORY
chroot chroot/ /bin/bash /chroot.steps.part.2.sh

umount -lf chroot/dev/
rm chroot/root/.bash_history
rm chroot/chroot.steps.part.1.sh chroot/chroot.steps.part.2.sh

mkdir -p image/casper image/isolinux image/install
cp chroot/boot/vmlinuz-3.2.*-generic image/casper/vmlinuz
cp chroot/boot/initrd.img-3.2.*-generic image/casper/initrd.lz
cp /usr/lib/syslinux/vesamenu.c32 /usr/lib/syslinux/isolinux.bin image/isolinux/
cp /boot/memtest86+.bin image/install/memtest

# Create manifest
chroot chroot dpkg-query -W --showformat='${Package} ${Version}\n' | tee image/casper/filesystem.manifest
cp -v image/casper/filesystem.manifest image/casper/filesystem.manifest-desktop
REMOVE='ubiquity ubiquity-frontend-gtk ubiquity-frontend-kde casper lupin-casper live-initramfs user-setup discover xresprobe os-prober libdebian-installer4'
for i in $REMOVE; do
  sed -i "/${i}/d" image/casper/filesystem.manifest-desktop
done

cat << EOF > image/README.diskdefines
#define DISKNAME Redo Backup
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
echo "http://redobackup.org" > release_notes_url
cd ../..

rm -rf image/casper/filesystem.squashfs redo.iso
mksquashfs chroot image/casper/filesystem.squashfs -e boot
printf $(sudo du -sx --block-size=1 chroot | cut -f1) > image/casper/filesystem.size
cd image
find . -type f -print0 | xargs -0 md5sum | grep -v "./md5sum.txt" > md5sum.txt

# Create ISO image (part 1/2), with -boot-info-table modifying isolinux.bin with 56-byte "boot information table" # at offset 8 in the file."
# See `man mkisofs` for more information. This modification invalidates the isolinux.bin md5sum calculated above.
mkisofs -r -V "Redo Backup" -cache-inodes -J -l -b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -o ../redo.iso . 

# Generate fresh md5sum containing the -boot-info-table modified isolinux.bin
find . -type f -print0 | xargs -0 md5sum | grep -v "./md5sum.txt" > md5sum.txt
# Create ISO image (part 2/2), the --boot-info-table modification has already been made to isolinux.bin, so the md5sum remains correct this time.
rm ../redo.iso
mkisofs -r -V "Redo Backup" -cache-inodes -J -l -b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -o ../redo.iso . 
cd ..

# TODO: Evaluate the "Errata" sections of the Redo Backup and Recovery
# TODO: Sourceforge Wiki, and determine if the build scripts need modification.
