#!/bin/bash

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

# One-higher than directory containing this build script
BASEDIR="$(git rev-parse --show-toplevel)"

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
