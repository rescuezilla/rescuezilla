# ----------------------------------------------------------------------
#   Copyright (C) 2003-2025 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2019-2025 Rescuezilla.com <rescuezilla@gmail.com>
# ----------------------------------------------------------------------
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------
import json
import unittest
from collections import OrderedDict

from parser.blkid import Blkid
from parser.os_prober import OsProber
from parser.parted import Parted
from parser.sfdisk import Sfdisk
from parser.combined_drive_state import CombinedDriveState

"""
This script contains a test that has been updated in association with the helper test script
update_test_combined_drive_state.sh, using snapshot-style testing.

"""


class CombinedDriveStateTest(unittest.TestCase):
    def test_combined_drive_state(self):
        parted_dict_dict = {}
        sfdict_dict_dict = {}

        # Output of "lsblk -o KNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL --paths --bytes --json"
        lsblk_json_output = """{
   "blockdevices": [
      {
         "kname": "/dev/loop0",
         "name": "/dev/loop0",
         "size": 1364275200,
         "type": "loop",
         "fstype": "squashfs",
         "mountpoint": "/rofs",
         "model": null,
         "serial": null
      },{
         "kname": "/dev/sda",
         "name": "/dev/sda",
         "size": 13194139533312,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB00000000-01000000"
      },{
         "kname": "/dev/sdb",
         "name": "/dev/sdb",
         "size": 1073741824,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB11111111-11111111"
      },{
         "kname": "/dev/sdc",
         "name": "/dev/sdc",
         "size": 2147483648,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB22222222-22222222"
      },{
         "kname": "/dev/sdd",
         "name": "/dev/sdd",
         "size": 8589934592,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB88888888-88888888",
         "children": [
            {
               "kname": "/dev/sdd1",
               "name": "/dev/sdd1",
               "size": 536870912,
               "type": "part",
               "fstype": "vfat",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdd2",
               "name": "/dev/sdd2",
               "size": 511705088,
               "type": "part",
               "fstype": "ext2",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdd3",
               "name": "/dev/sdd3",
               "size": 7539261440,
               "type": "part",
               "fstype": "crypto_LUKS",
               "mountpoint": null,
               "model": null,
               "serial": null
            }
         ]
      },{
         "kname": "/dev/sde",
         "name": "/dev/sde",
         "size": 17179869184,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB16161616-16161616",
         "children": [
            {
               "kname": "/dev/sde1",
               "name": "/dev/sde1",
               "size": 1073741824,
               "type": "part",
               "fstype": "ext4",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sde2",
               "name": "/dev/sde2",
               "size": 16105078784,
               "type": "part",
               "fstype": "LVM2_member",
               "mountpoint": null,
               "model": null,
               "serial": null,
               "children": [
                  {
                     "kname": "/dev/dm-0",
                     "name": "/dev/mapper/cl-swap",
                     "size": 1719664640,
                     "type": "lvm",
                     "fstype": "swap",
                     "mountpoint": null,
                     "model": null,
                     "serial": null
                  },{
                     "kname": "/dev/dm-1",
                     "name": "/dev/mapper/cl-root",
                     "size": 14382268416,
                     "type": "lvm",
                     "fstype": "xfs",
                     "mountpoint": null,
                     "model": null,
                     "serial": null
                  }
               ]
            }
         ]
      },{
         "kname": "/dev/sdf",
         "name": "/dev/sdf",
         "size": 53687091200,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB50505050-50505050",
         "children": [
            {
               "kname": "/dev/sdf1",
               "name": "/dev/sdf1",
               "size": 104857600,
               "type": "part",
               "fstype": "vfat",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdf2",
               "name": "/dev/sdf2",
               "size": 16777216,
               "type": "part",
               "fstype": null,
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdf3",
               "name": "/dev/sdf3",
               "size": 53040090624,
               "type": "part",
               "fstype": "ntfs",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdf4",
               "name": "/dev/sdf4",
               "size": 522190848,
               "type": "part",
               "fstype": "ntfs",
               "mountpoint": null,
               "model": null,
               "serial": null
            }
         ]
      },{
         "kname": "/dev/sdg",
         "name": "/dev/sdg",
         "size": 2199022206976,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB00000000-00000000",
         "children": [
            {
               "kname": "/dev/sdg1",
               "name": "/dev/sdg1",
               "size": 607125504,
               "type": "part",
               "fstype": "ntfs",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdg2",
               "name": "/dev/sdg2",
               "size": 2198412984320,
               "type": "part",
               "fstype": "ntfs",
               "mountpoint": null,
               "model": null,
               "serial": null
            }
         ]
      },{
         "kname": "/dev/sdh",
         "name": "/dev/sdh",
         "size": 2199022206976,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB22222222-22222222",
         "children": [
            {
               "kname": "/dev/sdh1",
               "name": "/dev/sdh1",
               "size": 607125504,
               "type": "part",
               "fstype": "ntfs",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdh2",
               "name": "/dev/sdh2",
               "size": 1097999899136,
               "type": "part",
               "fstype": "ntfs",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdh3",
               "name": "/dev/sdh3",
               "size": 536870912,
               "type": "part",
               "fstype": "vfat",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdh4",
               "name": "/dev/sdh4",
               "size": 1024,
               "type": "part",
               "fstype": null,
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdh5",
               "name": "/dev/sdh5",
               "size": 1099874435072,
               "type": "part",
               "fstype": "ext4",
               "mountpoint": null,
               "model": null,
               "serial": null
            }
         ]
      },{
         "kname": "/dev/sdi",
         "name": "/dev/sdi",
         "size": 1099511627776,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": "VBOX HARDDISK",
         "serial": "VB19491949-49194919",
         "children": [
            {
               "kname": "/dev/sdi1",
               "name": "/dev/sdi1",
               "size": 1073741824,
               "type": "part",
               "fstype": "ext4",
               "mountpoint": null,
               "model": null,
               "serial": null
            },{
               "kname": "/dev/sdi2",
               "name": "/dev/sdi2",
               "size": 1098436837376,
               "type": "part",
               "fstype": "btrfs",
               "mountpoint": null,
               "model": null,
               "serial": null
            }
         ]
      },{
         "kname": "/dev/sr0",
         "name": "/dev/sr0",
         "size": 1498515456,
         "type": "rom",
         "fstype": "iso9660",
         "mountpoint": "/cdrom",
         "model": "VBOX CD-ROM",
         "serial": "VB2-01700376"
      },{
         "kname": "/dev/nbd0",
         "name": "/dev/nbd0",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd1",
         "name": "/dev/nbd1",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd2",
         "name": "/dev/nbd2",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd3",
         "name": "/dev/nbd3",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd4",
         "name": "/dev/nbd4",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd5",
         "name": "/dev/nbd5",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd6",
         "name": "/dev/nbd6",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd7",
         "name": "/dev/nbd7",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd8",
         "name": "/dev/nbd8",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd9",
         "name": "/dev/nbd9",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd10",
         "name": "/dev/nbd10",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd11",
         "name": "/dev/nbd11",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd12",
         "name": "/dev/nbd12",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd13",
         "name": "/dev/nbd13",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd14",
         "name": "/dev/nbd14",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      },{
         "kname": "/dev/nbd15",
         "name": "/dev/nbd15",
         "size": 0,
         "type": "disk",
         "fstype": null,
         "mountpoint": null,
         "model": null,
         "serial": null
      }
   ]
}"""
        lsblk_json_dict = json.loads(lsblk_json_output)

        # Output of "blkid"
        blkid_dict = Blkid.parse_blkid_output("""/dev/mapper/cl-root: UUID="cf005336-1e5f-4bea-8ce3-cc6d5fa28df9" BLOCK_SIZE="512" TYPE="xfs"
/dev/sdd1: UUID="6FFE-1080" BLOCK_SIZE="512" TYPE="vfat" PARTUUID="c0870fb5-d41b-478b-9867-ace6d9cddc12"
/dev/sdd2: UUID="ed1a4c78-bd0c-4bad-a8ed-34b34f291ca3" BLOCK_SIZE="1024" TYPE="ext2" PARTUUID="0f233523-d9d7-4b05-83b5-124cdb0ab5d4"
/dev/sde1: UUID="75a460dc-7968-4391-ad99-2c9112e8d301" BLOCK_SIZE="4096" TYPE="ext4" PARTUUID="52c7e4ee-01"
/dev/sdf1: UUID="020A-12E6" BLOCK_SIZE="512" TYPE="vfat" PARTLABEL="EFI system partition" PARTUUID="33693f0a-a0cd-445a-b177-78d40714defd"
/dev/sdf3: BLOCK_SIZE="512" UUID="BABE0AE1BE0A9653" TYPE="ntfs" PARTLABEL="Basic data partition" PARTUUID="70571ec1-b70d-4288-8a15-9cd2bc88c9b6"
/dev/sdf4: BLOCK_SIZE="512" UUID="AE9C597D9C59414F" TYPE="ntfs" PARTUUID="d2b713e3-de15-46d3-bf44-f5e250c92c1a"
/dev/sdg1: LABEL="System Reserved" BLOCK_SIZE="512" UUID="FE6EE7E36EE79327" TYPE="ntfs" PARTUUID="d9bc7d71-01"
/dev/sdg2: BLOCK_SIZE="512" UUID="1496E88F96E87322" TYPE="ntfs" PARTUUID="d9bc7d71-02"
/dev/sdh1: LABEL="System Reserved" BLOCK_SIZE="512" UUID="FE6EE7E36EE79327" TYPE="ntfs" PARTUUID="d9bc7d71-01"
/dev/sdh2: BLOCK_SIZE="512" UUID="1496E88F96E87322" TYPE="ntfs" PARTUUID="d9bc7d71-02"
/dev/sdh3: UUID="1DD7-0310" BLOCK_SIZE="512" TYPE="vfat" PARTUUID="d9bc7d71-03"
/dev/sdh5: UUID="3a630c1f-2f80-499b-853d-a3bffe1d919b" BLOCK_SIZE="4096" TYPE="ext4" PARTUUID="d9bc7d71-05"
/dev/sdi1: UUID="c5774f90-0818-4671-8103-c9b0ae6a4b9d" BLOCK_SIZE="4096" TYPE="ext4" PARTUUID="44f3879f-01"
/dev/sdi2: LABEL="fedora_localhost-live" UUID="f139f46d-5f03-49bb-aa5c-397e702dce37" UUID_SUB="9f4aa3c0-a614-4902-96bc-7860743af362" BLOCK_SIZE="4096" TYPE="btrfs" PARTUUID="44f3879f-02"
/dev/sr0: BLOCK_SIZE="2048" UUID="2025-07-16-21-40-26-00" LABEL="Rescuezilla" TYPE="iso9660" PTTYPE="PMBR"
/dev/sdd3: UUID="be3d1af8-6624-4e0a-945e-587b0d88241e" TYPE="crypto_LUKS" PARTUUID="234da887-b633-480a-b7d4-8fb8e9812b0e"
/dev/sde2: UUID="N1kMfD-1i8G-M0hV-olxp-5EEW-4vX9-wqUMGx" TYPE="LVM2_member" PARTUUID="52c7e4ee-02"
/dev/loop0: BLOCK_SIZE="1048576" TYPE="squashfs"
/dev/mapper/cl-swap: UUID="fe6a6057-021f-46ef-b5b6-13042a1afc26" TYPE="swap"
/dev/sdf2: PARTLABEL="Microsoft reserved partition" PARTUUID="a8ec603c-50e5-4c53-8cd9-042b2612043a"
""")

        # Output of "os-prober"
        osprober_dict = OsProber.parse_os_prober_output("""
        /dev/sdg1:Windows 10:Windows:chain
/dev/sdh1:Windows 10:Windows1:chain
/dev/sdh5:Ubuntu 20.04.2 LTS (20.04):Ubuntu:linux
/dev/mapper/cl-root:CentOS Linux 8 (Core):CentOS:linux
""")

        # Output of 'sfdisk --dump /dev/sdX'
        sfdict_dict_dict["/dev/sda"] = Sfdisk.parse_sfdisk_dump_output("""
        
""")
        sfdict_dict_dict["/dev/sdb"] = Sfdisk.parse_sfdisk_dump_output("""
        
""")
        sfdict_dict_dict["/dev/sdc"] = Sfdisk.parse_sfdisk_dump_output("""
        
""")
        sfdict_dict_dict["/dev/sdd"] = Sfdisk.parse_sfdisk_dump_output("""
        label: gpt
label-id: 27AA6842-0569-412E-B83C-C6ABB02EF979
device: /dev/sdd
unit: sectors
first-lba: 34
last-lba: 16777182
sector-size: 512

/dev/sdd1 : start=        2048, size=     1048576, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, uuid=C0870FB5-D41B-478B-9867-ACE6D9CDDC12
/dev/sdd2 : start=     1050624, size=      999424, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=0F233523-D9D7-4B05-83B5-124CDB0AB5D4
/dev/sdd3 : start=     2050048, size=    14725120, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=234DA887-B633-480A-B7D4-8FB8E9812B0E
""")
        sfdict_dict_dict["/dev/sde"] = Sfdisk.parse_sfdisk_dump_output("""
        label: dos
label-id: 0x52c7e4ee
device: /dev/sde
unit: sectors
sector-size: 512

/dev/sde1 : start=        2048, size=     2097152, type=83, bootable
/dev/sde2 : start=     2099200, size=    31455232, type=8e
""")
        sfdict_dict_dict["/dev/sdf"] = Sfdisk.parse_sfdisk_dump_output("""
        label: gpt
label-id: 3932C36A-FA86-43B8-B03A-CD56195B74D4
device: /dev/sdf
unit: sectors
first-lba: 34
last-lba: 104857566
sector-size: 512

/dev/sdf1 : start=        2048, size=      204800, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, uuid=33693F0A-A0CD-445A-B177-78D40714DEFD, name="EFI system partition", attrs="GUID:63"
/dev/sdf2 : start=      206848, size=       32768, type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE, uuid=A8EC603C-50E5-4C53-8CD9-042B2612043A, name="Microsoft reserved partition", attrs="GUID:63"
/dev/sdf3 : start=      239616, size=   103593927, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=70571EC1-B70D-4288-8A15-9CD2BC88C9B6, name="Basic data partition"
/dev/sdf4 : start=   103833600, size=     1019904, type=DE94BBA4-06D1-4D40-A16A-BFD50179D6AC, uuid=D2B713E3-DE15-46D3-BF44-F5E250C92C1A, attrs="RequiredPartition GUID:63"
""")
        sfdict_dict_dict["/dev/sdg"] = Sfdisk.parse_sfdisk_dump_output("""
        label: dos
label-id: 0xd9bc7d71
device: /dev/sdg
unit: sectors
sector-size: 512

/dev/sdg1 : start=        2048, size=     1185792, type=7, bootable
/dev/sdg2 : start=     1187840, size=  4293775360, type=7
""")
        sfdict_dict_dict["/dev/sdh"] = Sfdisk.parse_sfdisk_dump_output("""
        label: dos
label-id: 0xd9bc7d71
device: /dev/sdh
unit: sectors
sector-size: 512

/dev/sdh1 : start=        2048, size=     1185792, type=7, bootable
/dev/sdh2 : start=     1187840, size=  2144531053, type=7
/dev/sdh3 : start=  2145720320, size=     1048576, type=b
/dev/sdh4 : start=  2146770942, size=  2148192258, type=5
/dev/sdh5 : start=  2146770944, size=  2148192256, type=83
""")
        sfdict_dict_dict["/dev/sdi"] = Sfdisk.parse_sfdisk_dump_output("""
        label: dos
label-id: 0x44f3879f
device: /dev/sdi
unit: sectors
sector-size: 512

/dev/sdi1 : start=        2048, size=     2097152, type=83, bootable
/dev/sdi2 : start=     2099200, size=  2145384448, type=83
""")

        parted_dict_dict["/dev/sda"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sda: 13194139533312B
Sector size (logical/physical): 512B/512B
Partition Table: unknown
Disk Flags: 
""")

        parted_dict_dict["/dev/sdb"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdb: 1073741824B
Sector size (logical/physical): 512B/512B
Partition Table: unknown
Disk Flags: 
""")

        parted_dict_dict["/dev/sdc"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdc: 2147483648B
Sector size (logical/physical): 512B/512B
Partition Table: unknown
Disk Flags: 
""")

        parted_dict_dict["/dev/sdd"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdd: 8589934592B
Sector size (logical/physical): 512B/512B
Partition Table: gpt
Disk Flags: 

Number  Start        End          Size         File system  Name  Flags
 1      1048576B     537919487B   536870912B   fat32              boot, esp
 2      537919488B   1049624575B  511705088B   ext2
 3      1049624576B  8588886015B  7539261440B
""")

        parted_dict_dict["/dev/sde"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sde: 17179869184B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags: 

Number  Start        End           Size          Type     File system  Flags
 1      1048576B     1074790399B   1073741824B   primary  ext4         boot
 2      1074790400B  17179869183B  16105078784B  primary               lvm
""")

        parted_dict_dict["/dev/sdf"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdf: 53687091200B
Sector size (logical/physical): 512B/512B
Partition Table: gpt
Disk Flags: 

Number  Start         End           Size          File system  Name                          Flags
 1      1048576B      105906175B    104857600B    fat32        EFI system partition          boot, esp, no_automount
 2      105906176B    122683391B    16777216B                  Microsoft reserved partition  msftres, no_automount
 3      122683392B    53162774015B  53040090624B  ntfs         Basic data partition          msftdata
 4      53162803200B  53684994047B  522190848B    ntfs                                       hidden, diag, no_automount
""")

        parted_dict_dict["/dev/sdg"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdg: 2199022206976B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags: 

Number  Start       End             Size            Type     File system  Flags
 1      1048576B    608174079B      607125504B      primary  ntfs         boot
 2      608174080B  2199021158399B  2198412984320B  primary  ntfs
""")

        parted_dict_dict["/dev/sdh"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdh: 2199022206976B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags: 

Number  Start           End             Size            Type      File system  Flags
 1      1048576B        608174079B      607125504B      primary   ntfs         boot
 2      608174080B      1098608073215B  1097999899136B  primary   ntfs
 3      1098608803840B  1099145674751B  536870912B      primary   fat32
 4      1099146722304B  2199021158399B  1099874436096B  extended
 5      1099146723328B  2199021158399B  1099874435072B  logical   ext4
""")

        parted_dict_dict["/dev/sdi"] = Parted.parse_parted_output("""
        Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdi: 1099511627776B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags: 

Number  Start        End             Size            Type     File system  Flags
 1      1048576B     1074790399B     1073741824B     primary  ext4         boot
 2      1074790400B  1099511627775B  1098436837376B  primary  btrfs
""")

        combined_drive_state_dict = (
            CombinedDriveState.construct_combined_drive_state_dict(
                lsblk_json_dict,
                blkid_dict,
                osprober_dict,
                parted_dict_dict,
                sfdict_dict_dict,
            )
        )
        expected_combined_drive_state_dict = OrderedDict(
            [
                (
                    "/dev/loop0",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 1364275200),
                            ("type", "loop"),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/loop0",
                                            {
                                                "filesystem": "squashfs",
                                                "size": 1364275200,
                                            },
                                        )
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/sda",
                    OrderedDict(
                        [
                            ("partition_table", "unknown"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB00000000-01000000"),
                            ("capacity", 13194139533312),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                        ]
                    ),
                ),
                (
                    "/dev/sdb",
                    OrderedDict(
                        [
                            ("partition_table", "unknown"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB11111111-11111111"),
                            ("capacity", 1073741824),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                        ]
                    ),
                ),
                (
                    "/dev/sdc",
                    OrderedDict(
                        [
                            ("partition_table", "unknown"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB22222222-22222222"),
                            ("capacity", 2147483648),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                        ]
                    ),
                ),
                (
                    "/dev/sdd",
                    OrderedDict(
                        [
                            ("partition_table", "gpt"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB88888888-88888888"),
                            ("capacity", 8589934592),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/sdd1",
                                            {
                                                "end": 537919487,
                                                "filesystem": "vfat",
                                                "flags": "boot, esp",
                                                "size": 536870912,
                                                "start": 1048576,
                                                "type": "part",
                                                "uuid": "6FFE-1080",
                                            },
                                        ),
                                        (
                                            "/dev/sdd2",
                                            {
                                                "end": 1049624575,
                                                "filesystem": "ext2",
                                                "flags": "",
                                                "size": 511705088,
                                                "start": 537919488,
                                                "type": "part",
                                                "uuid": "ed1a4c78-bd0c-4bad-a8ed-34b34f291ca3",
                                            },
                                        ),
                                        (
                                            "/dev/sdd3",
                                            {
                                                "end": 8588886015,
                                                "filesystem": "crypto_LUKS",
                                                "flags": "",
                                                "size": 7539261440,
                                                "start": 1049624576,
                                                "type": "part",
                                                "uuid": "be3d1af8-6624-4e0a-945e-587b0d88241e",
                                            },
                                        ),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/sde",
                    OrderedDict(
                        [
                            ("partition_table", "msdos"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB16161616-16161616"),
                            ("capacity", 17179869184),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/sde1",
                                            {
                                                "end": 1074790399,
                                                "filesystem": "ext4",
                                                "flags": "boot",
                                                "size": 1073741824,
                                                "start": 1048576,
                                                "type": "primary",
                                                "uuid": "75a460dc-7968-4391-ad99-2c9112e8d301",
                                            },
                                        ),
                                        (
                                            "/dev/sde2",
                                            {
                                                "end": 17179869183,
                                                "filesystem": "LVM2_member",
                                                "flags": "lvm",
                                                "size": 16105078784,
                                                "start": 1074790400,
                                                "type": "primary",
                                                "uuid": "N1kMfD-1i8G-M0hV-olxp-5EEW-4vX9-wqUMGx",
                                            },
                                        ),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/sdf",
                    OrderedDict(
                        [
                            ("partition_table", "gpt"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB50505050-50505050"),
                            ("capacity", 53687091200),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/sdf1",
                                            {
                                                "end": 105906175,
                                                "filesystem": "vfat",
                                                "flags": "boot, esp, no_automount",
                                                "size": 104857600,
                                                "start": 1048576,
                                                "type": "part",
                                                "uuid": "020A-12E6",
                                            },
                                        ),
                                        (
                                            "/dev/sdf2",
                                            {
                                                "end": 122683391,
                                                "filesystem": "MS_Reserved_Partition",
                                                "flags": "msftres, no_automount",
                                                "size": 16777216,
                                                "start": 105906176,
                                                "type": "part",
                                            },
                                        ),
                                        (
                                            "/dev/sdf3",
                                            {
                                                "end": 53162774015,
                                                "filesystem": "ntfs",
                                                "flags": "msftdata",
                                                "size": 53040090624,
                                                "start": 122683392,
                                                "type": "part",
                                                "uuid": "BABE0AE1BE0A9653",
                                            },
                                        ),
                                        (
                                            "/dev/sdf4",
                                            {
                                                "end": 53684994047,
                                                "filesystem": "ntfs",
                                                "flags": "hidden, diag, no_automount",
                                                "size": 522190848,
                                                "start": 53162803200,
                                                "type": "part",
                                                "uuid": "AE9C597D9C59414F",
                                            },
                                        ),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/sdg",
                    OrderedDict(
                        [
                            ("partition_table", "msdos"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB00000000-00000000"),
                            ("capacity", 2199022206976),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/sdg1",
                                            {
                                                "end": 608174079,
                                                "filesystem": "ntfs",
                                                "flags": "boot",
                                                "label": "System Reserved",
                                                "size": 607125504,
                                                "start": 1048576,
                                                "type": "primary",
                                                "uuid": "FE6EE7E36EE79327",
                                            },
                                        ),
                                        (
                                            "/dev/sdg2",
                                            {
                                                "end": 2199021158399,
                                                "filesystem": "ntfs",
                                                "flags": "",
                                                "size": 2198412984320,
                                                "start": 608174080,
                                                "type": "primary",
                                                "uuid": "1496E88F96E87322",
                                            },
                                        ),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/sdh",
                    OrderedDict(
                        [
                            ("partition_table", "msdos"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB22222222-22222222"),
                            ("capacity", 2199022206976),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/sdh1",
                                            {
                                                "end": 608174079,
                                                "filesystem": "ntfs",
                                                "flags": "boot",
                                                "label": "System Reserved",
                                                "os_bootloader": {
                                                    "os_description": "Windows 10",
                                                    "os_label": "Windows1",
                                                    "os_type": "chain",
                                                },
                                                "size": 607125504,
                                                "start": 1048576,
                                                "type": "primary",
                                                "uuid": "FE6EE7E36EE79327",
                                            },
                                        ),
                                        (
                                            "/dev/sdh2",
                                            {
                                                "end": 1098608073215,
                                                "filesystem": "ntfs",
                                                "flags": "",
                                                "size": 1097999899136,
                                                "start": 608174080,
                                                "type": "primary",
                                                "uuid": "1496E88F96E87322",
                                            },
                                        ),
                                        (
                                            "/dev/sdh3",
                                            {
                                                "end": 1099145674751,
                                                "filesystem": "vfat",
                                                "flags": "",
                                                "size": 536870912,
                                                "start": 1098608803840,
                                                "type": "primary",
                                                "uuid": "1DD7-0310",
                                            },
                                        ),
                                        (
                                            "/dev/sdh4",
                                            {
                                                "end": 2199021158399,
                                                "filesystem": "",
                                                "flags": "",
                                                "size": 1024,
                                                "start": 1099146722304,
                                                "type": "extended",
                                            },
                                        ),
                                        (
                                            "/dev/sdh5",
                                            {
                                                "end": 2199021158399,
                                                "filesystem": "ext4",
                                                "flags": "",
                                                "os_bootloader": {
                                                    "os_description": "Ubuntu "
                                                    "20.04.2 "
                                                    "LTS "
                                                    "(20.04)",
                                                    "os_label": "Ubuntu",
                                                    "os_type": "linux",
                                                },
                                                "size": 1099874435072,
                                                "start": 1099146723328,
                                                "type": "logical",
                                                "uuid": "3a630c1f-2f80-499b-853d-a3bffe1d919b",
                                            },
                                        ),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/sdi",
                    OrderedDict(
                        [
                            ("partition_table", "msdos"),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX HARDDISK"),
                            ("serial", "VB19491949-49194919"),
                            ("capacity", 1099511627776),
                            ("type", "disk"),
                            ("flags", " "),
                            ("logical_sector_size", 512),
                            ("physical_sector_size", 512),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/sdi1",
                                            {
                                                "end": 1074790399,
                                                "filesystem": "ext4",
                                                "flags": "boot",
                                                "size": 1073741824,
                                                "start": 1048576,
                                                "type": "primary",
                                                "uuid": "c5774f90-0818-4671-8103-c9b0ae6a4b9d",
                                            },
                                        ),
                                        (
                                            "/dev/sdi2",
                                            {
                                                "end": 1099511627775,
                                                "filesystem": "btrfs",
                                                "flags": "",
                                                "label": "fedora_localhost-live",
                                                "size": 1098436837376,
                                                "start": 1074790400,
                                                "type": "primary",
                                                "uuid": "f139f46d-5f03-49bb-aa5c-397e702dce37",
                                            },
                                        ),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/sr0",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", "VBOX CD-ROM"),
                            ("serial", "VB2-01700376"),
                            ("capacity", 1498515456),
                            ("type", "rom"),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/sr0",
                                            {
                                                "filesystem": "iso9660",
                                                "label": "Rescuezilla",
                                                "size": 1498515456,
                                                "uuid": "2025-07-16-21-40-26-00",
                                            },
                                        )
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd0",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd0", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd1",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd1", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd2",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd2", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd3",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd3", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd4",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd4", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd5",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd5", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd6",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd6", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd7",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd7", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd8",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd8", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd9",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd9", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd10",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd10", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd11",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd11", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd12",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd12", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd13",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd13", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd14",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd14", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/nbd15",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 0),
                            ("type", "disk"),
                            (
                                "partitions",
                                OrderedDict(
                                    [("/dev/nbd15", {"filesystem": "", "size": 0})]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/mapper/cl-swap",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 1719664640),
                            ("type", "lvm"),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/mapper/cl-swap",
                                            {
                                                "filesystem": "swap",
                                                "size": 1719664640,
                                                "uuid": "fe6a6057-021f-46ef-b5b6-13042a1afc26",
                                            },
                                        )
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                (
                    "/dev/mapper/cl-root",
                    OrderedDict(
                        [
                            ("partition_table", None),
                            ("has_raid_member_filesystem", False),
                            ("model", None),
                            ("serial", None),
                            ("capacity", 14382268416),
                            ("type", "lvm"),
                            (
                                "partitions",
                                OrderedDict(
                                    [
                                        (
                                            "/dev/mapper/cl-root",
                                            {
                                                "filesystem": "xfs",
                                                "os_bootloader": {
                                                    "os_description": "CentOS "
                                                    "Linux "
                                                    "8 "
                                                    "(Core)",
                                                    "os_label": "CentOS",
                                                    "os_type": "linux",
                                                },
                                                "size": 14382268416,
                                                "uuid": "cf005336-1e5f-4bea-8ce3-cc6d5fa28df9",
                                            },
                                        )
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
            ]
        )
        self.assertDictEqual(
            expected_combined_drive_state_dict, combined_drive_state_dict
        )
