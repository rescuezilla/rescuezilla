#!/bin/bash

# Echo each command
set -x

# Directory containing this build script
BASEDIR=$(cd $(dirname $(readlink -f "$0"))/../ && pwd)

git config --global --add safe.directory ${BASEDIR}
git config --global --add safe.directory ${BASEDIR}/src/third-party/partclone-latest
git config --global --add safe.directory ${BASEDIR}/src/third-party/partclone.v0.2.43
git config --global --add safe.directory ${BASEDIR}/src/third-party/util-linux
