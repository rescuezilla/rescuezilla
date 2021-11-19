# Directory containing this build script
INTEGRATION_TEST_FOLDER=$(dirname $(readlink -f "$0"))/../
cd "$INTEGRATION_TEST_FOLDER"
# Get IP
TARGET_IP=`./integration_test.py listip --vm $VM`

run_cmd_in_rescuezilla_vm() {
    TARGET_IP="$1"
    RUN_CMD_IN_VM="$2"

    # Note: Production builds of Rescuezilla do not have openssh-server installed (or a pre-authorized SSH key configured with ssh-copy-id)

    SSH_SERVER="ubuntu@$TARGET_IP"
    ssh-keygen -R $TARGET_IP
    # Copy a script to detect if the machine is a VirtualBox VM, and also to mount the VirtualBox shared folder
    scp -o "CheckHostIP=no" -o "StrictHostKeyChecking=no" "scripts/is_virtualbox_vm.sh" $SSH_SERVER:/tmp/
    # DANGER: Run a command within the VM. The command could be eg, restoring a backup on to /dev/sda, which can be very dangerous.
    # Notice there are two key protections against accidentally overwriting the wrong SSH server: it is connecting as the ubuntu user
    # with a pretrusted SSH key, and the careful syntax which first checks for whether the machine the command is being run on is a VM.
    ssh -o "CheckHostIP=no" -o "StrictHostKeyChecking=no" -t $SSH_SERVER "/tmp/is_virtualbox_vm.sh && sudo $RUN_CMD_IN_VM"
    if [ $? -ne 0 ]; then
        echo "Test failed"
        exit 1
    fi
}

# Boot Rescuezilla
boot_dvd() {
     VM="$1"
     ISO_PATH="${2:-$INTEGRATION_TEST_FOLDER/../../build/rescuezilla.amd64.impish.iso}"
     ISO_CHECK_MATCH="${3:-Ubuntu 21.10}"
     ./integration_test.py stop --vm $VM
     ./integration_test.py insertdvd --vm $VM --path-to-dvd "$ISO_PATH"
     ./integration_test.py start --vm $VM
     # Check to confirm Rescuezilla environment is online
     ./integration_test.py check --vm $VM --contains "$ISO_CHECK_MATCH"
     # It takes time for the Ubuntu user account to be generated
     # TODO: Improve this solution
     sleep 5
}

check_primary_os_boots() {
    VM="$1"
    VM_CHECK_MATCH="$2"
    ./integration_test.py stop --vm $VM
    sleep 1
    ./integration_test.py removedvd --vm $VM
    if [ $? -ne 0 ]; then
        echo "Could not remove DVD."
        return 1
    fi
    ./integration_test.py start --vm $VM
    ./integration_test.py check --vm $VM --contains "$VM_CHECK_MATCH"
    CHECK_STATUS=$?
    ./integration_test.py stop --vm $VM
    return $CHECK_STATUS
}

backup_restore_test() {
    TEST_PREFIX="$1"
    CLONEZILLA_IMAGE_NAME="Clonezilla.$TEST_PREFIX.Image"
    VM_NAME="$2"
    ISO_PATH="$3"
    ISO_CHECK_MATCH="$4"
    PRIMARY_OS_CHECK_MATCH="$5"
    TARGET_IP=`./integration_test.py listip --vm $VM_NAME`

    VM_INFO="\"$VM_NAME\" ($CLONEZILLA_IMAGE_NAME) with boot check: \"$PRIMARY_OS_CHECK_MATCH\""
    echo "Starting backup/restore test for $VM_INFO"

    # Reset VM state to working CentOS environment
    ./integration_test.py stop --vm $VM_NAME
    ./integration_test.py reset --vm $VM_NAME
    ./integration_test.py deploy --vm $VM_NAME

    boot_dvd "$VM_NAME"

    CLONEZILLA_IMAGE_PATH="/mnt/rescuezilla.shared.folder/$CLONEZILLA_IMAGE_NAME"
    echo "Delete previous Clonezilla image from within the VM $CLONEZILLA_IMAGE_PATH"
    run_cmd_in_rescuezilla_vm $TARGET_IP "rm -rf $CLONEZILLA_IMAGE_PATH"
    # Backup using Clonezilla
    run_cmd_in_rescuezilla_vm $TARGET_IP "ocs_live_batch=yes /usr/sbin/ocs-sr -q2 -j2 -z1 -i 4096 -sfsck -senc -p command savedisk $CLONEZILLA_IMAGE_NAME sda"

    # Stop and reset VM to zeroed disk
    ./integration_test.py stop --vm $VM_NAME
    ./integration_test.py reset --vm $VM_NAME

    # Boot Rescuezilla
    boot_dvd "$VM_NAME" "$ISO_PATH" "$ISO_CHECK_MATCH"

    # Restore using Clonezilla
    run_cmd_in_rescuezilla_vm $TARGET_IP "ocs_live_batch=yes /usr/sbin/ocs-sr -g auto -e1 auto -e2 -r -j2 -p cmd restoredisk $CLONEZILLA_IMAGE_NAME sda"

    # Check primary OS boots
    check_primary_os_boots "$VM_NAME" "$PRIMARY_OS_CHECK_MATCH"
    RC=$?
    if [ $? -eq 0 ]; then
        echo "Test success: $VM_INFO"
        exit 0
    else
        echo "Test failed: $VM_INFO"
        exit 1
    fi
}

