#!/bin/bash
#
# Helper script which generates a text file containing a checksum of the files
# within an ISO image.  This includes both the file in the ISO9660 filesystem,
# and the squashfs compressed root filesystem contained within it. This
# checksum file is very useful for comparing an officially released ISO image
# to an ISO built from source (using the graphical diff tool 'meld' and
# 'diff'), for auditing the correctness of an official release.
#  
# Note: The analysis using 'meld' provides an indication of what differs, which
# suggest what areas to manually investigate further. An alternative form of
# analysis involves booting each ISO image and running `dpkg-query --list` to
# list all installed packages, and comparing the output. Differences may be
# attributable to use of backports and updates APT repositories, which get
# updated with new versions of packages during the support window of an Ubuntu
# release.
#
# Usage:          ./checksum_iso_image.sh path.to.iso.image
#
# Graphical diff: meld file1.txt file2.txt
#
# Dependencies: squashfs-tools
# Suggested: meld

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root."
   exit 1
fi

# e: Exit on non-zero error code
# x: Echo each command that executes
set -ex

PATH_TO_ISO_IMAGE=$1
ISO_IMAGE_FILENAME=$(basename -- "$PATH_TO_ISO_IMAGE")
HASH_FUNCTION=sha1sum
BASE_DIR=$(dirname "$(readlink -f "$0")")
PATH_TO_CHECKSUM_FILE=$BASE_DIR/$ISO_IMAGE_FILENAME.$HASH_FUNCTION.txt

MOUNT_DIR=$(mktemp --directory --suffix $ISO_IMAGE_FILENAME)
SQUASHFS_UNPACK_DIR=$(mktemp --directory --suffix $ISO_IMAGE_FILENAME.extracted)/squashfs

function cleanup {
    cd $BASE_DIR
    rm -rf SQUASHFS_UNPACK_DIR
    umount $MOUNT_DIR
    rm -rf $MOUNT_DIR
}
# Register the cleanup function to be executed on exit
# Comment trap registration out if you wish to examine the extracted directories manually.
trap cleanup EXIT

mount "$PATH_TO_ISO_IMAGE" "$MOUNT_DIR"
pushd "$MOUNT_DIR"
printf "ISO9660 filesystem:\n" > "$PATH_TO_CHECKSUM_FILE"
echo "Checksumming ISO9660 filesystem. This may take some time..."
find . -type f -exec $HASH_FUNCTION {} \; >> "$PATH_TO_CHECKSUM_FILE"
popd

sudo unsquashfs -dest "$SQUASHFS_UNPACK_DIR/" "$MOUNT_DIR/casper/filesystem.squashfs"
pushd "$SQUASHFS_UNPACK_DIR"
printf "\nUnpacked squashfs filesystem:\n" >> "$PATH_TO_CHECKSUM_FILE"
echo "Checksumming unpacked squashfs filesystem. This may take some time..."
find . -type f -exec $HASH_FUNCTION {} \; >> "$PATH_TO_CHECKSUM_FILE"
popd

echo "Checksums written to $PATH_TO_CHECKSUM_FILE successfully!"
