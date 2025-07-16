#!/bin/bash
#
# Script to construct the release commit for the Rescuezilla website, to minimize manual effort.
#
# This script:
#
# * Updates the Rescuezilla website static HTML with the relevant version number
#
# Note: the script relies on the Rescuezilla GitHub Pages repo being a sibling folder to the current git repository

if [ $# -lt 2 ]; then
    echo "Usage: ./update-website.sh <version> <default variant name> [optional override date released]"
    echo "Example: ./update-website.sh 2.6 \"oracular\""
    echo "Example: ./update-website.sh 2.6 \"oracular\" 2025-07-14"
    exit 1
fi

set -x

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
SCRIPT_NAME=$(basename "$0")
BASEDIR="$(git rev-parse --show-toplevel)"

RESCUEZILLA_WEBSITE_DIR="${BASEDIR}/../rescuezilla.github.io"

# Source utility functions
source "${SCRIPT_DIR}/utilities.sh"

VERSION="$1"
DEFAULT_VARIANT_NAME="$2"
DATE_RELEASED="${3:-$(date '+%Y-%m-%d')}"
UPDATED_BRANCH_NAME="update-website-temporary-branch"

FILENAME="rescuezilla-$VERSION-64bit.$DEFAULT_VARIANT_NAME.iso"
URL="https://github.com/rescuezilla/rescuezilla/releases/download/$VERSION/$FILENAME"

# Yes, it's silly to use sed to update HTML directly over a rendered website, but it worked well enough.
update_website_html() {
    local version="$1"
    local default_variant_name="$2"
    local date_released="$3"

    # Update main landing page with version and release date
    sed -i "s|<h2>Download Version .*</h2>|<h2>Download Version $version</h2>|g" "${RESCUEZILLA_WEBSITE_DIR}/index.html"
    sed -i "s|>Released .*<|>Released $date_released<|g" "${RESCUEZILLA_WEBSITE_DIR}/index.html"
    git add "${RESCUEZILLA_WEBSITE_DIR}/index.html"

    # Update the download link
    sed -i "s|https://github.com/rescuezilla/rescuezilla/releases/download/.*/rescuezilla-.*.iso|$URL\">$FILENAME</a>|g" "${RESCUEZILLA_WEBSITE_DIR}/download.html"
    git add "${RESCUEZILLA_WEBSITE_DIR}/download.html"
}


create_git_commit() {
    local version="$1"
    local script_name="$2"
    # Create the changelog entry
    cat <<EOF > /tmp/commitmsg
Updates webpage for Rescuezilla v$version

Commit created by $script_name in the Rescuezilla main repository.
EOF
    echo "Commit message: $(cat /tmp/commitmsg)"
    git commit -F /tmp/commitmsg
}

# Create the git branch for the release
cd $RESCUEZILLA_WEBSITE_DIR && do_git_branch "$UPDATED_BRANCH_NAME" origin/master

update_website_html "$VERSION" "$DEFAULT_VARIANT_NAME" "$DATE_RELEASED"

create_git_commit "$VERSION" "$SCRIPT_NAME"

echo "Completed  Please review the changes on branch $UPDATED_BRANCH_NAME in repository $RESCUEZILLA_WEBSITE_DIR and validate that the updates are correct, and push after release made public on GitHub."
echo "Reminder: Use 'python -m http.server' to preview the changes locally."
