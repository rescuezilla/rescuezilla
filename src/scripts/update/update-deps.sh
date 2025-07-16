#!/bin/bash
#
# Script to automatically update Rescuezilla's dependencies with minimal manual effort,
# creating the relevant git commits on local branch forked from latest master branch).
#
# The developer invoking this script then should review the changes (eg, using `tig`),
# and launch automated testing
#
# This script updates the:
#
# * Weblate translations
#     * merging from a forked repo of Rescuezilla hosted by Weblate.Org)
# * src/third-party/debootstrap
# *    local git submodule containing the tool used for Debian/Ubuntu image construction
# * src/third-party/partclone-latest
# *    local git submodule containing the tool used for the fundamental filesystem imaging
#
# Usage:
# * ./update-deps.sh
#
# Note: the script does a checkout to a new branch. If the script fails, simply:
# 1. git checkout master
# 2. git submodule update --init --recursive
# 3. Rerun the script (if appropriate)
#
# git submodules can be tricky to work with, so validate with commands like `git status`, `git branch`,
# or the tool `tig`
#
# Once you are happy with the changes, validate them (eg, using the imperfect integration test suite)
# and then apply the changes on master branch eg, a `git reset --hard update.sh-script-temporary-branch`

if [ $# -ne 0 ]; then
    echo "Usage: ./update-deps.sh"
    echo "This script takes no arguments"
    exit 1
fi

set -x

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
SCRIPT_NAME=$(basename "$0")
BASEDIR="$(git rev-parse --show-toplevel)"

UPDATED_BRANCH_NAME="update.sh-script-temporary-branch"

# Source utility functions
source "${SCRIPT_DIR}/utilities.sh"

# Get the most recently created tag.
# his will typically be the latest release, but it's not guaranteed.
most_recent_tag() {
    git for-each-ref --sort=-creatordate --format '%(refname:short)' refs/tags | head -n 1
}

# Get the commit date in ISO format. eg, 2025-06-04
commit_date_iso() {
    git log -1 --format=%cd --date=format:'%Y-%m-%d'
}

# Get the commit date in human-readable format. eg, June 2025
commit_date_readable() {
    git log -1 --format=%cd --date=format:'%B %Y'
}

# Add a string to the end of the current (unreleased) release's CHANGELOG.md
# This requires CHANGELOG.md to have an entry for the unreleased/upcoming version.
append_to_changelog() {
    LINE_TO_INSERT="$1"
    # Get the line number of *second* line starting with '#', which is the Markdown heading
    # marker corresponding to the previous release
    previous_release_heading=$(grep -n '^#' CHANGELOG.md | sed -n '2p' | cut -d: -f1)
    insertion_line=$((previous_release_heading - 1))
    sed --in-place "${insertion_line}i$LINE_TO_INSERT" "${BASEDIR}/CHANGELOG.md"
    git add "${BASEDIR}/CHANGELOG.md"
}

# Update weblate translations by fetching the latest changes from the Weblate git remote and creating a merge commit
# Note: Rescuezilla typically uses a git rebase-workflow, but (for better or worse) tends to use merge commits to
# delineate translations and other bigger single-feature branches
update_weblate_translations() {
    temp_branch="weblate-update"
    git remote add weblate https://hosted.weblate.org/git/rescuezilla/rescuezilla/
    git fetch weblate

    # Create merge commit message
    cat <<EOF > /tmp/mergemsg
Merge remote-tracking branch 'weblate/master'
EOF
    # Create merge commit
    git merge --no-ff -F /tmp/mergemsg weblate/master
}

# Helper function to update a submodule to its latest tag
update_submodule_to_latest_tag() {
    local submodule_name="$1"
    echo "Updating $submodule_name..."
    
    # Fetch latest changes
    git fetch origin
    
    local latest_tag=$(most_recent_tag)
    echo "Checkout $submodule_name to $latest_tag"
    
    # Checkout latest tag
    git checkout "$latest_tag"
}

# Update git submodules
update_submodules() {
    # List of submodules to update. Excludes util-linux (used for sfdisk backwards compatibility), and partclone-utils (unused in favor of partclone-nbd)
    local submodules=(
        "debootstrap"
        "partclone-latest"
        "partclone-nbd"
    )

    local current_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "no-tag")

    # Update each submodule
    echo "Checkout $submodule_name to $latest_tag"
    for submodule in "${submodules[@]}"; do
        cd "$BASEDIR/src/third-party/$submodule" && {
            previous_commit_description=$(git describe --tags --abbrev=0 2>/dev/null || echo "error")
            previous_commit_date_iso=$(commit_date_iso)
            previous_commit_date_readable=$(commit_date_readable)
            update_submodule_to_latest_tag "$submodule"
            new_tag=$(most_recent_tag)
            new_tag_date_iso=$(commit_date_iso)
            new_tag_date_readable=$(commit_date_readable)
        }
        cd "$BASEDIR"
        git add "$BASEDIR/src/third-party/$submodule"

        echo "For partclone, we need to bump the package version"
        extra_commit_msg=""
        if [ "$submodule" == "partclone-latest" ]; then
            # Partclone also needs its Makefile version string updated
            sed --in-place "s/PARTCLONE_PKG_VERSION=.*/PARTCLONE_PKG_VERSION=$new_tag/" Makefile

            # Extra info for the commit message with intentional multi-line assignment for git commit hard linebreak
            extra_commit_msg="Additionally bumps Makefile checkinstall package version
environment variable, and updates the CHANGELOG.md"
            git add Makefile

            # If there are staged changes based on the `git add` above, let's add an entry to the CHANGELOG.md too. 
            if ! git diff --cached --quiet; then
                 # And update the 'CHANGELOG.md' too
                 changelog_message="* Upgraded to latest partclone \`$new_tag\` (released $new_tag_date_readable) from partclone \`$previous_commit_description\` (released $previous_commit_date_readable)"
                 append_to_changelog "$changelog_message"
            fi
        fi

        a="${SCRIPT_DIR}/${SCRIPT_NAME}"
        script_rel_path="${a#${BASEDIR}}"
        # Write commit message (including commit-message style line-breaks)
        cat <<EOF > /tmp/commitmsg
Bump $submodule to $new_tag(from $previous_commit_description)

Bumps $submodule from $previous_commit_description ($previous_commit_date_iso)
to $new_tag ($new_tag_date_iso).

$extra_commit_msg

Commit created by ./$script_rel_path
EOF
        git commit -F /tmp/commitmsg
    done
}

# Create the git branch for the update
do_git_branch "$UPDATED_BRANCH_NAME" origin/master

# Execute both updates
update_weblate_translations
update_submodules

echo "Completed updating weblate translations and submodules. Please review the changes on branch $UPDATED_BRANCH_NAME and validate that the updates are correct, and push when ready."
