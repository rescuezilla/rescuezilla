#!/bin/bash

# Only run if called from inside a VM
if [[ -z "$(dmidecode | grep -i "Product Name: VirtualBox")" ]]
then
    echo "WARNING: no VM detected!"
    echo "Refusing to run to avoid to corrupt the partitions."
    exit 1
fi >&2

# 2nd check to protect developer environment
if [[ $1 != "doit" ]]
then
    echo "WARNING! Magic keyword missing; aborting." >&2
    exit 42
fi

cat << EOF | sfdisk /dev/sda
label: dos
label-id: 0x16787f0b
device: /dev/sda
unit: sectors
sector-size: 512

/dev/sda1 : start=        2048, size=      204800, type=83, bootable
/dev/sda2 : start=      206848, size=      409600, type=83
/dev/sda3 : start=      616448, size=      409600, type=b
/dev/sda4 : start=     1026048, size=    15357952, type=5
/dev/sda5 : start=     1028096, size=      409600, type=7
EOF

cat << EOF | sfdisk /dev/sdb
label: gpt
label-id: 07121DFB-DD43-2E4B-B492-5B358C373205
device: /dev/sdb
unit: sectors
first-lba: 2048
last-lba: 16383966
sector-size: 512

/dev/sdb1 : start=        2048, size=      204800, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=72BE5BC4-0EEB-8642-9F63-A3FA7203F8C5
/dev/sdb2 : start=      206848, size=      409600, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=696A73B3-E7BB-1348-8091-6F44D605307D
/dev/sdb3 : start=      616448, size=      409600, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=35300CDA-2507-C74F-9A2C-08D3BDD9D4D0
/dev/sdb4 : start=     1026048, size=      409600, type=0657FD6D-A4AB-43C4-84E5-0933C84B4F4F, uuid=473A9E65-9066-1242-9CC9-3F80BBAE58B2
/dev/sdb5 : start=     1435648, size=      409600, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=9C8FE3B3-185E-734C-9EFD-C0B37DC897C9
/dev/sdb6 : start=     1845248, size=      102400, type=00DEAD00-D0D0-FEED-F00D-00DEADBEEF00, uuid=BC8FE393-0000-C0C0-0000-B37DC897C900
EOF

partprobe

# Format the partitions

mkfs.ext2 -L BootExt2   /dev/sda1
mkfs.ext4 -L RootExt4   /dev/sda2
mkfs.vfat -n DATA_FAT32 /dev/sda3
mkfs.ntfs -L DATA_NTFS  /dev/sda5

mkfs.exfat   -n exFAT   /dev/sdb1
mkfs.btrfs   -L BTRFS   /dev/sdb2
mkfs.reiser4 -L REISER4 /dev/sdb3
mkfs.xfs     -L XFS     /dev/sdb5

# Copy some data in the partitions

mkdir -p dst
for d in a b
do
    for p in 1 2 3 5
    do
        mount /dev/sd$d$p dst &&
        rsync -aq /rofs/usr/bin dst/
        umount dst
    done
done
rmdir dst
