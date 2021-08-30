#!/bin/bash
#
# Rescuezilla integration test: Windows EFI

# Source in utility function
. $(dirname $(readlink -f "$0"))/utility.fn.sh

ISO_PATH="${1:-$INTEGRATION_TEST_FOLDER/../../build/rescuezilla.amd64.hirsute.iso}"
ISO_CHECK_MATCH="${2:-Ubuntu 21.04}"

backup_restore_test "Windows.10.BIOS" "Rescuezilla.2tb.Primary.BIOS" "$ISO_PATH" "$ISO_CHECK_MATCH" "Windows 10"
