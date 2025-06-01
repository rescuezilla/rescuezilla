#!/bin/bash

# Echo each command
set -x

source common.bash

if [ "$CODENAME" = "INVALID" ] || [ "$ARCH" = "INVALID" ]; then
  echo "The variable CODENAME=${CODENAME} or ARCH=${ARCH} was not set correctly. Are you using the Makefile? Please consult build instructions."
  exit 1
fi

# Disable the debootstrap GPG validation for Ubuntu 18.04 (Bionic) after its public key
# failed to validate on the Docker build environment container for an unclear reason.
# See [1] for full write-up.
#
# [1] https://github.com/rescuezilla/rescuezilla/issues/538
GPG_CHECK_OPTS=""
if [ "$CODENAME" = "bionic" ]; then
    GPG_CHECK_OPTS="--no-check-gpg"
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
    DEBOOTSTRAP_DIR=${DEBOOTSTRAP_SCRIPT_DIRECTORY} ./debootstrap ${GPG_CHECK_OPTS} --arch=$ARCH \
    --foreign $CODENAME $TARGET_FOLDER http://ftp.us.debian.org/debian
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
chroot $BUILD_DIRECTORY/chroot/ /bin/bash -c "DEBOOTSTRAP_DIR=\"debootstrap\" ./debootstrap/debootstrap --second-stage ${GPG_CHECK_OPTS}"
RET=$?
if [[ $RET -ne 0 ]]; then
    echo "debootstrap part 2/2 failed. This may occur if the package cache ($PKG_CACHE_DIRECTORY/$DEBOOTSTRAP_CACHE_DIRECTORY/)"
    echo "exists but is not fully populated. If so, deleting this directory might help. Please consult the build instructions." 
    exit 1
fi
