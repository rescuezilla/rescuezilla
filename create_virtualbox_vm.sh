#!/bin/bash

MACHINENAME=${1?Please provide a name for the vm}

if [ ! -f ./rescuezilla-*.iso ];
then
    VERSION=2.1.3
    wget "https://github.com/rescuezilla/rescuezilla/releases/download/$VERSION/rescuezilla-$VERSION-64bit.groovy.iso"
fi

# Select Iso
ISO_NAME="$(ls *.iso | tail -1)"

# Create VM
VBoxManage createvm --name $MACHINENAME --ostype "Debian_64" --register --basefolder "$(pwd)"

# Set memory and network
VBoxManage modifyvm $MACHINENAME --ioapic on
VBoxManage modifyvm $MACHINENAME --memory 2048 --vram 128
VBoxManage modifyvm $MACHINENAME --nic1 nat

# Create Disk and connect Iso
VBoxManage storagectl $MACHINENAME --name "SATA Controller" --add sata --controller IntelAhci
VBoxManage createhd --filename "$(pwd)/$MACHINENAME/sda.vdi" --size 8000 --format VDI
VBoxManage storageattach $MACHINENAME --storagectl "SATA Controller" --port 0 --device 0 --type hdd --medium "$(pwd)/$MACHINENAME/sda.vdi"
VBoxManage createhd --filename "$(pwd)/$MACHINENAME/sdb.vdi" --size 8000 --format VDI
VBoxManage storageattach $MACHINENAME --storagectl "SATA Controller" --port 1 --device 0 --type hdd --medium "$(pwd)/$MACHINENAME/sdb.vdi"

VBoxManage storagectl $MACHINENAME --name "IDE Controller" --add ide --controller PIIX4
VBoxManage storageattach $MACHINENAME --storagectl "IDE Controller" --port 1 --device 0 --type dvddrive --medium "$(pwd)/$ISO_NAME"
VBoxManage modifyvm $MACHINENAME --boot1 dvd --boot2 disk --boot3 none --boot4 none

# Require the VirtualBox Guest Additions

# Enable RDP
VBoxManage modifyvm $MACHINENAME --vrde on
VBoxManage modifyvm $MACHINENAME --vrdemulticon on --vrdeport 10001

# Share the local shared/ directory with the VM
# - to access: mkdir shared; mount -t vboxsf shared shared
mkdir -p shared
VBoxManage sharedfolder add $MACHINENAME -name shared -hostpath "$PWD/shared" --automount

# Start the VM
#VBoxHeadless --startvm $MACHINENAME
