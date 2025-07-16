#!/bin/bash
#
# Script to construct the Rescuezilla release commit, to minimize manual effort.
#
# This script:
#
# * Adds a deb-package CHANGELOG entry to 'rescuezilla' and 'graphical-shutdown'
#     * Debian has limitations around acceptable version strings, so prefer
#       simple version strings in the form of 'x.y' and 'x.y.z'
# * Updates date information in the top-level CHANGELOG.md file
# * Deletes any old git tag, and creates a new tagged commit for the release
# 
# Usage:
# * ./create-release.sh <version> <remote branch name>
#
# Note: the script does a checkout to a new branch. If the script fails, simply:
# 1. git checkout master
# 2. Rerun the script (if appropriate)
#
# Note: the git tag is used by the deb package build scripts through
# "git describe --tags --abbrev=0"
#
# The developer invoking this script then should then sanity-check the changes (eg, using `tig`).
# In additional to building the ISO image locally. Before interacting with the main GitHub repository
# to eg create a PR, it's suggested developers to push the branch to a FORK of the Rescuzilla GitHub
# repository so your forked of GitHub Actions workflow will build everything on GitHub Actions
# infrastructure, including uploading a new release your GitHub fork.


if [ $# -lt 2 ]; then
    echo "Usage: ./create-release.sh <version> <remote branch name>"
    echo "Example: ./create-release.sh 2.6 origin/master"
    exit 1
fi

set -x

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
SCRIPT_NAME=$(basename "$0")
BASEDIR="$(git rev-parse --show-toplevel)"

# Source utility functions
source "${SCRIPT_DIR}/utilities.sh"

VERSION="$1"
HUMAN_READABLE_DATE=$(date -R)
UPDATED_BRANCH_NAME="create-release-temporary-branch"

prepend_to_debian_changelog() {
    local version="$1"
    local human_readable_date="$2"
    local app_name="$3"
    local deb_changelog_path="$4"
    
    # Create the changelog entry
    cat <<EOF > /tmp/deb_changelog_entry
$app_name (${version}-1) unstable; urgency=low

  * New version. For full changes: See https://raw.githubusercontent.com/rescuezilla/rescuezilla/master/CHANGELOG.md

 -- $(git config user.name) <$(git config user.email)>  $human_readable_date

EOF
    
    # Prepend the new entry to the changelog file
    cat /tmp/deb_changelog_entry "$deb_changelog_path" > /tmp/combined_changelog
    mv /tmp/combined_changelog "$deb_changelog_path"
    
    # Stage the changes
    git add "$deb_changelog_path"
}


# Add a string to the end of the current (unreleased) release's CHANGELOG.md
# This requires CHANGELOG.md to have an entry for the unreleased/upcoming version.
update_changelog_md() {
    VERSION="$1"
    LINE_TO_SET="# Rescuezilla v$VERSION ($(date '+%Y-%m-%d'))"
    # Replace the first line of CHANGELOG.md
    sed --in-place "1s/.*/$LINE_TO_SET/" "${BASEDIR}/CHANGELOG.md"
    git add "${BASEDIR}/CHANGELOG.md"
}

create_tagged_git_commit() {
    local version="$1"
    
    # Create the changelog entry
    cat <<EOF > /tmp/commitmsg
Update CHANGELOG, pkgs for Rescuezilla v$version

Adds CHANGELOG entry for $version, and upgrades the debian package changelog entries
for the Rescuezilla frontend apps, so that things continue to build when this
commit is tagged.

Note: internally, the build scripts that generate the deb package version using
\`git describe --tags --abbrev=0\`, which sets the version number. Because of
this, the build will fail if the deb package changelog does not reflect the
most recent git tag output from the `git describe` command above.

This means for every commit to successfully build without a single commit
failing, it is this very commit that must be tagged as $version.

This commit was created by ${SCRIPT_NAME}
EOF
    git commit -F /tmp/commitmsg
    git tag "$version"
}

# Create the git branch for the release
do_git_branch "$UPDATED_BRANCH_NAME" "$REMOTE_BRANCH_NAME"

prepend_to_debian_changelog "$VERSION" "$HUMAN_READABLE_DATE" "rescuezilla" "${BASEDIR}/src/apps/rescuezilla/debian/changelog"
prepend_to_debian_changelog "$VERSION" "$HUMAN_READABLE_DATE" "graphical-shutdown" "${BASEDIR}/src/apps/graphical-shutdown/debian/changelog"

update_changelog_md "$VERSION"


# Delete existing tag if it exists
delete_local_tag_if_exists "$VERSION"
create_tagged_git_commit "$VERSION"

echo "Completed  Please review the changes on branch $UPDATED_BRANCH_NAME and validate that the updates are correct, and push when ready."
echo "If something went wrong, checkout your original branch and run 'git submodule update --init --recursive' and rerun the script."
echo ""
echo "If you have a fork configured, you can push this tag to it to sanity-check the on-tag GitHub Actions workflows using:"
echo " git push private -d $VERSION && git push private $VERSION"
