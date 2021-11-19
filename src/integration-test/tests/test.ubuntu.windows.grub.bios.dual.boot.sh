#!/bin/bash
#
# Rescuezilla integration test: Ubuntu/Windows dualboot BIOS

# Source in utility function
. $(dirname $(readlink -f "$0"))/utility.fn.sh

ISO_PATH="${1:-$INTEGRATION_TEST_FOLDER/../../build/rescuezilla.amd64.impish.iso}"
ISO_CHECK_MATCH="${2:-Ubuntu 21.10}"

backup_restore_test "Ubuntu.Windows.Dualboot.MBR" "Rescuezilla.2tb.Secondary.BIOS" "$ISO_PATH" "$ISO_CHECK_MATCH" "Ubuntu 20.04.2 LTS"

