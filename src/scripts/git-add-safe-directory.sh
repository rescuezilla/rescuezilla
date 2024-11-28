#!/bin/bash
#
# Trust the Rescuezilla git repositories and git submodules so they can be
# parsed by git tooling.
#
# See `man git-config` entry for "safe.directory" for more details.
#
# This is required to be run whenever `git` command will be run (so the build scripts,
# and build environments such as Docker and the CI build bot), since it enables:
#
# * Identifying source code's root directory with git rev-parse
# * Querying the Rescuezilla version based on `git tag` and if necessary placing
#   a truncated in SHA in the built ISO image
# * etc
#
# It's also necessary for developers using git tooling in an interactive manner.

# Begin echo'ing each command
set -x

BASEDIR="$(dirname $(readlink -f "$0"))"
# Identify the git root directory using relative paths to the current script.
#
# Note: Unfortunately CANNOT get this from `git rev-parse --show-toplevel`, because
# we would first have needed to configure the 'safe.directory' to use that command :)
GIT_ROOT=$(cd "$BASEDIR/../../" && pwd)

. "$BASEDIR/lib.sh"

exit_if_missing_command git

# Trust base Rescuezilla git repository
git config --global --add safe.directory ${GIT_ROOT}

# Trust partclone git submodule
git config --global --add safe.directory ${GIT_ROOT}/src/third-party/partclone-latest

# DEPRECATED: Trust Redo Backup and Recovery v1.0.4 partclone submodule provided for
# maximum backwards compatibility
git config --global --add safe.directory ${GIT_ROOT}/src/third-party/partclone.v0.2.43

# Trust util-linux git submodule (used to compile latest version of sfdisk)
git config --global --add safe.directory ${GIT_ROOT}/src/third-party/util-linux
