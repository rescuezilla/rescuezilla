#!/bin/bash

set -x

# Exit with failure if this script is run outside a VirtualBox VM
if [[ -z "$(sudo dmidecode | grep -i "Product Name: VirtualBox")" ]]
then
    echo "WARNING: No VirtualBox VM detected!"
    echo "Refusing to run to avoid potentially overwriting partitions."
    exit 1
fi >&2

# Shared folder path within the VM
VM_SHARED_FOLDER=/mnt/rescuezilla.shared.folder

# Mount the VirtualBox Shared Folder so that guest VM can read/write
# to a path that's accessible by the host operating system
if [ ! -d "$VM_SHARED_FOLDER" ]; then
    echo "Directory $VM_SHARED_FOLDER does not exist, creating..."
    sudo mkdir -p "$VM_SHARED_FOLDER"
fi

# Check if mountpoint is already mounted
mountpoint -q "$VM_SHARED_FOLDER"
RC=$?
if [ $RC -ne 0 ]; then
    echo "Mountpoint $VM_SHARED_FOLDER is not mounted, mounting..."
    sudo mount -t vboxsf rescuezilla.shared.folder "$VM_SHARED_FOLDER"
    RC=$?
    if [ $RC -ne 0 ]; then
        echo "Failed to mount $VM_SHARED_FOLDER"
        exit 1
    fi
fi

sudo unlink /home/partimag
# Symlink the shared folder as the Clonezilla image repository
sudo ln -s "$VM_SHARED_FOLDER" /home/partimag
RC=$?
if [ $RC -ne 0 ]; then
    echo "Failed to link $VM_SHARED_FOLDER to /home/partimag"
    exit 1
fi

exit 0
