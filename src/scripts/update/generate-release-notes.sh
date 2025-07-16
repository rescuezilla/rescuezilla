#!/bin/bash
#
# Script to generate a draft of Rescuezilla release notes and write this to stdout.
#
# Usage:
# * ./generate-release-notes.sh <version> <iso_variant>

if [ $# -ne 2 ]; then
    echo "Usage: ./generate-release-notes.sh <version> <iso_variant>"
    echo "This script takes two arguments"
    exit 1
fi

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
SCRIPT_NAME=$(basename "$0")
BASEDIR="$(git rev-parse --show-toplevel)"

VERSION="$1"
ISO_VARIANT="$2"
ISO_NAME="rescuezilla-${VERSION}-64bit.${ISO_VARIANT}.iso"
URL="https://github.com/rescuezilla/rescuezilla/releases/download/$VERSION/$ISO_NAME"

function gather_changelog_contents {
    # Gather changelog contents
    local prev_version_changelog_line_num=$(egrep -n "^#\s*Rescuezilla" "${BASEDIR}/CHANGELOG.md" | sed -n '2p' | cut -d: -f1)
    if [ -n "$prev_version_changelog_line_num" ]; then
        prev_version_changelog_line_num=$((prev_version_changelog_line_num - 1))
        sed -n "1,${prev_version_changelog_line_num}p" "${BASEDIR}/CHANGELOG.md"
    fi
}

# Print the release notes from the CHANGELOG.md file, up to the next version
# Note: the next version is the first line starting with a number
cat <<EOF
**Download the 64-bit version of the Rescuezilla ${VERSION} version: [${ISO_NAME}](${URL})**

If you have a blank screen, try "Graphical Fallback Mode" from the Rescuezilla boot menu (after selecting a language). If that doesn't work, try the alternative ISO image. Each variant has slightly different video drivers and Linux kernel versions, so often have slightly different graphics support.

$(gather_changelog_contents)

Details of all previous releases available in the [changelog](https://raw.githubusercontent.com/rescuezilla/rescuezilla/master/CHANGELOG.md).

### Compatibility

Rescuezilla creates backups that are fully compatible with the industry-standard Clonezilla tool. Rescuezilla works with images created by:
* Clonezilla [*](https://github.com/rescuezilla/rescuezilla/issues/372)
* Rescuezilla
* Every virtual machine image format supported by the \`qemu-nbd\` utility. Eg,
  * VirtualBox's VDI
  * VMWare's VMDK
  * Qemu's QCOW2
  * Hyper-V's VHDx
  * raw .dd/.img
  * ...and more!
* Redo Rescue
* Foxclone
* FOG Project (still in-development: only supports Windows MBR/GPT disks due to FOG Project's more advanced image manipulation)
* FSArchiver (restore only, not explore)
* Apart GTK
* _Redo Backup and Recovery_ (v0.9.2 format, v0.9.3-v1.0.4 format and the old [community updates](https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#identifying-redo-backup-versions))

### Bug advisories

Please report any errors (ideally with logs) on the [GitHub issues page](https://github.com/rescuezilla/rescuezilla/issues?q=is%3Aopen+is%3Aissue+label%3Abug) (after searching for duplicate issues).

Rescuezilla is currently tested using an automated testing suite with a test matrix of Windows 10 and Linux environments, containing various disk layouts and system configurations on 64-bit Intel-compatible environments. The end-to-end integration test is run nightly with the results available on the [GitHub Actions](https://github.com/rescuezilla/rescuezilla/actions/workflows/run-integration-test-suite.yml). In addition to the automated testing suite, ad-hoc manual QA verification is done the author.

### Checksums

Checksums available in 'Assets' section at the bottom of this release file.

### Discussion and User Support

If you need support, start by checking the [frequently asked questions](https://rescuezilla.com/help.html), then proceed to the [Rescuezilla forum](https://sourceforge.net/p/rescuezilla/discussion/).

### Reviews and Testimonials

**You can read reviews of Rescuezilla on [AlternativeTo](https://alternativeto.net/software/rescuezilla/reviews/)**. Please consider joining AlternativeTo and giving the project a like.

Download: [${ISO_NAME}](${URL})
EOF