#!/bin/bash
#
# Rescuezilla integration test: CentOS8 disk is an MBR + LVM (Logical Volume Manager)

set -o pipefail
set -x

# Directory containing this build script
BASEDIR=$(dirname $(readlink -f "$0"))

# Git root directory
GIT_ROOT_DIR="$(git rev-parse --show-toplevel)"

ISO_BASE_PATH="${1:-"$GIT_ROOT_DIR/build"}"
LOG_BASE_PATH="${2:-"$BASEDIR"}"

# Mapping between the ISO image filename and the ISO check
declare -A expected_version
expected_version["rescuezilla.amd64.noble.iso"]="Ubuntu 24.04"
expected_version["rescuezilla.amd64.mantic.iso"]="Ubuntu 23.10"
expected_version["rescuezilla.amd64.oracular.iso"]="Ubuntu 24.10"
expected_version["rescuezilla.amd64.jammy.iso"]="Ubuntu 22.04"
expected_version["rescuezilla.amd64.focal.iso"]="Ubuntu 20.04"
expected_version["rescuezilla.i386.bionic.iso"]="Ubuntu 18.04"

execute_all_tests() {
    ISO_PATH="$1"
    ISO_CHECK_MATCH="$2"

    for test_script in "${BASEDIR}"/test*.sh; do
        echo " ------ Running tests against $iso_filename"
        log_path="$LOG_BASE_PATH/$(basename $test_script).log_file.txt"
        echo "Run tests. Follow the log files using: tail -f $log_path"
        /usr/bin/time bash -x "$test_script" "$ISO_PATH" "$ISO_CHECK_MATCH" | tee "$log_path"
        exit_code=$?
        echo "Exit code code for $test_script run with $ISO_PATH was $?"
        if [ $exit_code -ne 0 ]; then
            exit $exit_code
        fi
    done
}

# Loop over the associative array and print key-value pairs
for iso_filename in "${!expected_version[@]}"; do
    iso_path="$ISO_BASE_PATH/$iso_filename"
    echo " --- Running tests against $iso_path"
    if [ ! -e "$iso_path" ]; then
        echo "Error: File '$iso_path' does not exist. Skipping this ISO"
    else
        execute_all_tests "$iso_path" "${iso_filename[$key]}"
    fi
done


