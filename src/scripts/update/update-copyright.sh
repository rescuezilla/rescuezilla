#!/bin/bash
#
# Script to update the copyright year across the source code, so each of the find/replace commands
# don't need to run manually.
#
# Usage:
# * ./update-copyright.sh <end year>
#
# Note: the script does a checkout to a new branch. If the script fails, simply:
# 1. git checkout master
# 2. Rerun the script (if appropriate)


if [ $# -lt 1 ]; then
    echo "Usage: ./update-copyright.sh <end year>"
    echo "Example: ./update-copyright.sh 2025"
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
UPDATED_BRANCH_NAME="update-copyright-temporary-branch"

find_replace_with_git() {
    local find_string="$1"
    local replace_string="$2"
    local file_path="$3"
    
    git grep -l "$find_string" "$file_path" | xargs sed -i "s/$find_string/$replace_string/g"
}

update_copyright() {
    # Note: we deliberately ignore the Weblate translations, and let Weblate manage its updates

    local end_year="$1"

    cd "${BASEDIR}"

    # Match for a four-digit year
    group_match='\([0-9]\{4\}\)'

    find_replace_with_git "${group_match}-[0-9]* Rescuezilla.com <rescuezilla@gmail.com>" "\1-$end_year Rescuezilla.com <rescuezilla@gmail.com>" "${BASEDIR}"
    # Also update the copyright year for Clonezilla's main author, as maintaining compatibility with Clonezilla is updated through a close reading of the Clonezilla source code directly.
    find_replace_with_git "${group_match}-[0-9]* Steven Shiau <steven _at_ clonezilla org>" "\1-$end_year Steven Shiau <steven _at_ clonezilla org>" "${BASEDIR}"

    # Update the Debian package control file copyright too, which has different syntax
    find_replace_with_git "Copyright: ${group_match}-[0-9]* Shasheen Ediriweera <rescuezilla@gmail.com>" "Copyright: \1-$end_year Shasheen Ediriweera <rescuezilla@gmail.com>" "${BASEDIR}"
}


create_git_commit() {
    local end_year="$1"

    git add -u :/
    
    # Create the changelog entry
    cat <<EOF > /tmp/commitmsg
Updates copyright date to $end_year

Updates all relevant copyright dates to $end_year.

This commit was created by ${SCRIPT_NAME}
EOF
    git commit -F /tmp/commitmsg
}

# Create the git branch for the release
do_git_branch "$UPDATED_BRANCH_NAME" "master"

update_copyright "$VERSION"

create_git_commit "$VERSION"


echo "Completed. Please review the changes on branch $UPDATED_BRANCH_NAME and validate that the updates are correct, and push when ready."
echo "If something went wrong, checkout your original branch and rerun the script."
