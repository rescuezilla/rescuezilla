# ----------------------------------------------------------------------
#   Copyright (C) 2003-2021 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2019-2021 Rescuezilla.com <rescuezilla@gmail.com>
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
import pprint
import unittest

from parser.blkid import Blkid
from parser.combined_drive_state import CombinedDriveState
from parser.os_prober import OsProber
from parser.parted import Parted
from parser.sfdisk import Sfdisk


class CombinedDriveStateTest(unittest.TestCase):
    def test_combined_drive_state(self):
        parted_dict_dict = {}
        sfdict_dict_dict = {}

        lsblk_json_output = """{
   "blockdevices": [
      {"kname":"/dev/loop0", "name":"/dev/loop0", "size":698761216, "type":"loop", "fstype":"squashfs", "mountpoint":"/rofs", "model":null},
      {"kname":"/dev/sda", "name":"/dev/sda", "size":34359738368, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sda1", "name":"/dev/sda1", "size":34357641216, "type":"part", "fstype":"ntfs", "mountpoint":"/mnt/backup", "model":null}
         ]
      },
      {"kname":"/dev/sdb", "name":"/dev/sdb", "size":1073741824, "type":"disk", "fstype":"LVM2_member", "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/dm-0", "name":"/dev/mapper/vgtest-lvtest", "size":1069547520, "type":"lvm", "fstype":"ext4", "mountpoint":null, "model":null}
         ]
      },
      {"kname":"/dev/sdc", "name":"/dev/sdc", "size":1610612736, "type":"disk", "fstype":"ntfs", "mountpoint":null, "model":"VBOX_HARDDISK"},
      {"kname":"/dev/sdd", "name":"/dev/sdd", "size":2147483648, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdd1", "name":"/dev/sdd1", "size":3145728, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd2", "name":"/dev/sdd2", "size":44040192, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd4", "name":"/dev/sdd4", "size":1024, "type":"part", "fstype":null, "mountpoint":null, "model":null},
            {"kname":"/dev/sdd5", "name":"/dev/sdd5", "size":12582912, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd6", "name":"/dev/sdd6", "size":4194304, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd7", "name":"/dev/sdd7", "size":28311552, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd8", "name":"/dev/sdd8", "size":4194304, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd9", "name":"/dev/sdd9", "size":20971520, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd10", "name":"/dev/sdd10", "size":83886080, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd11", "name":"/dev/sdd11", "size":72351744, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd12", "name":"/dev/sdd12", "size":18874368, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd13", "name":"/dev/sdd13", "size":29360128, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdd14", "name":"/dev/sdd14", "size":45088768, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null}
         ]
      },
      {"kname":"/dev/sde", "name":"/dev/sde", "size":2684354560, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sde1", "name":"/dev/sde1", "size":113246208, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sde2", "name":"/dev/sde2", "size":67108864, "type":"part", "fstype":"vfat", "mountpoint":null, "model":null},
            {"kname":"/dev/sde3", "name":"/dev/sde3", "size":2277507072, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sde4", "name":"/dev/sde4", "size":224395264, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null}
         ]
      },
      {"kname":"/dev/sdf", "name":"/dev/sdf", "size":3221225472, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdf1", "name":"/dev/sdf1", "size":268435456, "type":"part", "fstype":"btrfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf2", "name":"/dev/sdf2", "size":147849216, "type":"part", "fstype":"ext2", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf3", "name":"/dev/sdf3", "size":1024, "type":"part", "fstype":null, "mountpoint":null, "model":null},
            {"kname":"/dev/sdf5", "name":"/dev/sdf5", "size":52428800, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf6", "name":"/dev/sdf6", "size":34603008, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf7", "name":"/dev/sdf7", "size":73400320, "type":"part", "fstype":"vfat", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf8", "name":"/dev/sdf8", "size":47185920, "type":"part", "fstype":"vfat", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf9", "name":"/dev/sdf9", "size":55574528, "type":"part", "fstype":"reiser4", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf10", "name":"/dev/sdf10", "size":35651584, "type":"part", "fstype":"reiserfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf11", "name":"/dev/sdf11", "size":36700160, "type":"part", "fstype":"swap", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf12", "name":"/dev/sdf12", "size":379584512, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf13", "name":"/dev/sdf13", "size":45088768, "type":"part", "fstype":"udf", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf14", "name":"/dev/sdf14", "size":68157440, "type":"part", "fstype":"xfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf15", "name":"/dev/sdf15", "size":50331648, "type":"part", "fstype":null, "mountpoint":null, "model":null},
            {"kname":"/dev/sdf16", "name":"/dev/sdf16", "size":40894464, "type":"part", "fstype":null, "mountpoint":null, "model":null},
            {"kname":"/dev/sdf17", "name":"/dev/sdf17", "size":11534336, "type":"part", "fstype":"minix", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf18", "name":"/dev/sdf18", "size":62914560, "type":"part", "fstype":"f2fs", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf19", "name":"/dev/sdf19", "size":135266304, "type":"part", "fstype":"nilfs2", "mountpoint":null, "model":null},
            {"kname":"/dev/sdf20", "name":"/dev/sdf20", "size":1656750080, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null}
         ]
      },
      {"kname":"/dev/sdg", "name":"/dev/sdg", "size":3758096384, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK"},
      {"kname":"/dev/sdh", "name":"/dev/sdh", "size":4294967296, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdh1", "name":"/dev/sdh1", "size":104857600, "type":"part", "fstype":"LVM2_member", "mountpoint":null, "model":null,
               "children": [
                  {"kname":"/dev/dm-1", "name":"/dev/mapper/vgtest1-lvtest1", "size":54525952, "type":"lvm", "fstype":"vfat", "mountpoint":null, "model":null}
               ]
            },
            {"kname":"/dev/sdh2", "name":"/dev/sdh2", "size":104857600, "type":"part", "fstype":"LVM2_member", "mountpoint":null, "model":null,
               "children": [
                  {"kname":"/dev/dm-3", "name":"/dev/mapper/vgtest2-lvtest2", "size":54525952, "type":"lvm", "fstype":"ntfs", "mountpoint":null, "model":null}
               ]
            },
            {"kname":"/dev/sdh3", "name":"/dev/sdh3", "size":104857600, "type":"part", "fstype":"LVM2_member", "mountpoint":null, "model":null,
               "children": [
                  {"kname":"/dev/dm-2", "name":"/dev/mapper/vgtest3-lvtest3", "size":54525952, "type":"lvm", "fstype":"ext4", "mountpoint":null, "model":null}
               ]
            }
         ]
      },
      {"kname":"/dev/sdi", "name":"/dev/sdi", "size":8589934592, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdi1", "name":"/dev/sdi1", "size":536870912, "type":"part", "fstype":"vfat", "mountpoint":null, "model":null},
            {"kname":"/dev/sdi2", "name":"/dev/sdi2", "size":255852544, "type":"part", "fstype":"ext2", "mountpoint":null, "model":null},
            {"kname":"/dev/sdi3", "name":"/dev/sdi3", "size":7795113984, "type":"part", "fstype":"crypto_LUKS", "mountpoint":null, "model":null}
         ]
      },
      {"kname":"/dev/sdj", "name":"/dev/sdj", "size":53687091200, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdj1", "name":"/dev/sdj1", "size":554696704, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null},
            {"kname":"/dev/sdj2", "name":"/dev/sdj2", "size":104857600, "type":"part", "fstype":"vfat", "mountpoint":null, "model":null},
            {"kname":"/dev/sdj3", "name":"/dev/sdj3", "size":16777216, "type":"part", "fstype":null, "mountpoint":null, "model":null},
            {"kname":"/dev/sdj4", "name":"/dev/sdj4", "size":53008662528, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null}
         ]
      },
      {"kname":"/dev/sdk", "name":"/dev/sdk", "size":1073741824, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdk1", "name":"/dev/sdk1", "size":1072693248, "type":"part", "fstype":"linux_raid_member", "mountpoint":null, "model":null,
               "children": [
                  {"kname":"/dev/md127", "name":"/dev/md127", "size":1071644672, "type":"raid1", "fstype":"ext4", "mountpoint":null, "model":null}
               ]
            }
         ]
      },
      {"kname":"/dev/sdl", "name":"/dev/sdl", "size":1073741824, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdl1", "name":"/dev/sdl1", "size":1072693248, "type":"part", "fstype":"linux_raid_member", "mountpoint":null, "model":null,
               "children": [
                  {"kname":"/dev/md127", "name":"/dev/md127", "size":1071644672, "type":"raid1", "fstype":"ext4", "mountpoint":null, "model":null}
               ]
            }
         ]
      },
      {"kname":"/dev/sdm", "name":"/dev/sdm", "size":1073741824, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdm1", "name":"/dev/sdm1", "size":1072693248, "type":"part", "fstype":"linux_raid_member", "mountpoint":null, "model":null,
               "children": [
                  {"kname":"/dev/md0", "name":"/dev/md0", "size":1071644672, "type":"raid1", "fstype":"ext4", "mountpoint":null, "model":null}
               ]
            }
         ]
      },
      {"kname":"/dev/sdn", "name":"/dev/sdn", "size":1073741824, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
         "children": [
            {"kname":"/dev/sdn1", "name":"/dev/sdn1", "size":1072693248, "type":"part", "fstype":"linux_raid_member", "mountpoint":null, "model":null,
               "children": [
                  {"kname":"/dev/md0", "name":"/dev/md0", "size":1071644672, "type":"raid1", "fstype":"ext4", "mountpoint":null, "model":null}
               ]
            }
         ]
      },
      {"kname":"/dev/sdo", "name":"/dev/sdo", "size":1610612736, "type":"disk", "fstype":"ext4", "mountpoint":null, "model":"VBOX_HARDDISK"},
      {"kname":"/dev/sr0", "name":"/dev/sr0", "size":805623808, "type":"rom", "fstype":"iso9660", "mountpoint":"/cdrom", "model":"VBOX_CD-ROM"}
   ]
}"""

        lsblk_json_dict = json.loads(lsblk_json_output)

        input_blkid_string = """/dev/mapper/vgtest-lvtest: UUID="b9131c40-9742-416c-b019-8b11481a86ac" TYPE="ext4"
/dev/sda1: UUID="5C2F5F000C198BC5" TYPE="ntfs" PTTYPE="dos" PARTUUID="9aa1db09-6b7c-45a6-b392-c14518730297"
/dev/sdc: UUID="0818993868533997" TYPE="ntfs" PTTYPE="dos"
/dev/sdd1: UUID="925ef222-bc6d-4e46-a31d-af3443821ed6" TYPE="ext4" PARTUUID="1dbd2bfc-01"
/dev/sdd10: UUID="2708289c-c559-4d5c-bed1-98735f673bc0" TYPE="ext4" PARTUUID="1dbd2bfc-0a"
/dev/sdd11: UUID="c1dc5a1d-d22b-4a64-933f-5495a454eb05" TYPE="ext4" PARTUUID="1dbd2bfc-0b"
/dev/sdd12: UUID="47d1b78f-dd89-44d2-8af6-e7c01f1b635e" TYPE="ext4" PARTUUID="1dbd2bfc-0c"
/dev/sdd13: UUID="39fb1fdd-2cb8-449d-8d15-3eb7ab682677" TYPE="ext4" PARTUUID="1dbd2bfc-0d"
/dev/sdd14: UUID="f40bf79e-619e-422c-a546-ba78caa4ced7" TYPE="ext4" PARTUUID="1dbd2bfc-0e"
/dev/sdd2: UUID="206b6149-a675-4149-b368-8d7f158d9da2" TYPE="ext4" PARTUUID="1dbd2bfc-02"
/dev/sdd5: UUID="b8a96bc5-43c5-4180-a6c6-12466b544ced" TYPE="ext4" PARTUUID="1dbd2bfc-05"
/dev/sdd6: UUID="0897426b-24ee-47ed-8c85-e034205a43aa" TYPE="ext4" PARTUUID="1dbd2bfc-06"
/dev/sdd7: UUID="c4f8b878-1a4e-424b-93dd-17ea6d8e14d2" TYPE="ext4" PARTUUID="1dbd2bfc-07"
/dev/sdd8: UUID="e4fa2ad0-a206-447e-9c14-829d52c10407" TYPE="ext4" PARTUUID="1dbd2bfc-08"
/dev/sdd9: UUID="34648ad0-2fc1-47e1-8503-dc88b5152386" TYPE="ext4" PARTUUID="1dbd2bfc-09"
/dev/sde1: UUID="39DE69624116B96D" TYPE="ntfs" PTTYPE="dos" PARTUUID="4c6ec2cf-8de5-43c0-9757-41a596de5486"
/dev/sde2: UUID="B155-F891" TYPE="vfat" PARTUUID="be9f4179-560c-4bc9-8366-ae214f69a16e"
/dev/sde3: UUID="286C1DA536C63454" TYPE="ntfs" PTTYPE="dos" PARTUUID="363bdd4e-d6a1-42e6-a4da-616cd3e46952"
/dev/sde4: UUID="11d0533c-feba-4a07-ae30-7ff3720a051e" TYPE="ext4" PARTUUID="ced0279d-0096-4ebe-8425-4c6c9d46a4d2"
/dev/sdf1: UUID="c297cbb6-acb5-4d6a-9e34-af7558e120a0" UUID_SUB="695a452a-c43c-477c-8d5c-a21802e18091" TYPE="btrfs" PARTUUID="43c18652-01"
/dev/sdf12: UUID="023E47301DBC9964" TYPE="ntfs" PTTYPE="dos" PARTUUID="43c18652-0c"
/dev/sdf13: UUID="5f4b3897b65975a8" LABEL="LinuxUDF" TYPE="udf" PARTUUID="43c18652-0d"
/dev/sdf17: TYPE="minix" PARTUUID="43c18652-11"
/dev/sdf18: UUID="d73d2f4f-fba2-43ef-ad7a-c5fe877bf8a9" TYPE="f2fs" PARTUUID="43c18652-12"
/dev/sdf2: UUID="04944da2-d784-4c9f-b143-060d2776c4b1" TYPE="ext2" PARTUUID="43c18652-02"
/dev/sdf20: UUID="718E7F8E7F42D1B8" TYPE="ntfs" PTTYPE="dos" PARTUUID="43c18652-14"
/dev/sdf5: UUID="a2f8e4d6-ac83-4c57-a046-b7122c0398d5" TYPE="ext4" PARTUUID="43c18652-05"
/dev/sdf6: UUID="1297CD00121D448B" TYPE="ntfs" PTTYPE="dos" PARTUUID="43c18652-06"
/dev/sdf7: SEC_TYPE="msdos" UUID="CF57-1227" TYPE="vfat" PARTUUID="43c18652-07"
/dev/sdf8: UUID="CF6A-B2D0" TYPE="vfat" PARTUUID="43c18652-08"
/dev/sdi1: UUID="F5A2-3D31" TYPE="vfat" PARTUUID="b227e8b3-c8ea-448f-9657-53670575e6a8"
/dev/sdi2: UUID="80a2000c-c375-4a74-b6f9-2f1e1c7a8958" TYPE="ext2" PARTUUID="a3b889cb-31af-469d-a584-34edb323c62a"
/dev/sdj1: LABEL="Recovery" UUID="5C22168F22166E70" TYPE="ntfs" PARTLABEL="Basic data partition" PARTUUID="e3e94ae6-c2ab-495a-a955-a32140f56c2a"
/dev/sdj2: UUID="2C16-C81E" TYPE="vfat" PARTLABEL="EFI system partition" PARTUUID="7423670f-d0c3-4724-82f7-3185350a1bf7"
/dev/sdj4: UUID="DA40176E4017511D" TYPE="ntfs" PARTLABEL="Basic data partition" PARTUUID="1f1c6171-d10c-44c0-ba9b-e12995d7f4da"
/dev/sdk1: UUID="b4b3109e-816d-bcee-66c4-151e60fd8e23" UUID_SUB="cbb347a0-e478-39be-5dae-8b2955375ff6" LABEL="ubuntu:0" TYPE="linux_raid_member" PARTUUID="edb03a25-01"
/dev/sdl1: UUID="b4b3109e-816d-bcee-66c4-151e60fd8e23" UUID_SUB="17ee1620-2ccc-c266-1cd8-a567f6896d7a" LABEL="ubuntu:0" TYPE="linux_raid_member" PARTUUID="c6774609-01"
/dev/sr0: UUID="2020-09-04-10-27-14-00" LABEL="Rescuezilla" TYPE="iso9660" PTTYPE="PMBR"
/dev/loop0: TYPE="squashfs"
/dev/sdb: UUID="i20UTQ-OaX3-c6nB-CiBv-Gav1-hgVf-tEkO2W" TYPE="LVM2_member"
/dev/sdf9: UUID="0ab2eb0a-6c94-4f78-8206-7d725bbeb4e5" TYPE="reiser4" PARTUUID="43c18652-09"
/dev/sdf10: UUID="d230da2e-5359-43cb-827e-40c48a0a572b" TYPE="reiserfs" PARTUUID="43c18652-0a"
/dev/sdf11: UUID="217c8359-2ce6-4d07-bc44-4dcae84bc089" TYPE="swap" PARTUUID="43c18652-0b"
/dev/sdf14: UUID="3211b89b-b5ce-461d-8e6e-8acfaaa4bb28" TYPE="xfs" PARTUUID="43c18652-0e"
/dev/sdf19: UUID="957acceb-12f3-4574-ac1f-fb6e53f1a22f" TYPE="nilfs2" PARTUUID="43c18652-13"
/dev/sdh1: UUID="aNcRGF-4HyS-UoFu-aNpE-tXKI-nyeu-LiKaTm" TYPE="LVM2_member" PARTUUID="c64c40a3-4eec-4b86-820a-f8068ad3f686"
/dev/sdh2: UUID="cwuIbV-pb5s-9whu-eezX-WiZU-4wlY-gvuLZS" TYPE="LVM2_member" PARTUUID="45e285ea-caa3-4fc7-a7fe-9727d3198f09"
/dev/sdh3: UUID="jStAm5-tt1J-6uRa-HElo-EROm-DgjD-B5OJ3B" TYPE="LVM2_member" PARTUUID="4a014da5-75ca-45b2-9b62-7e3380c14570"
/dev/sdi3: UUID="17147edc-1e54-4300-b47a-01b138581512" TYPE="crypto_LUKS" PARTUUID="5f64fbd4-dcad-4467-8a8b-f3e009871661"
/dev/md127: UUID="0ca32d11-af2c-4512-9e68-bef318870149" TYPE="ext4"
/dev/mapper/vgtest1-lvtest1: SEC_TYPE="msdos" UUID="0559-959C" TYPE="vfat"
/dev/mapper/vgtest3-lvtest3: UUID="846a2cbd-b040-4afd-bb1c-8ecd6e15f0c2" TYPE="ext4"
/dev/mapper/vgtest2-lvtest2: UUID="588E895406ECC468" TYPE="ntfs" PTTYPE="dos"
/dev/sdf15: PARTUUID="43c18652-0f"
/dev/sdf16: PARTUUID="43c18652-10"
/dev/sdj3: PARTLABEL="Microsoft reserved partition" PARTUUID="229ef65d-3315-4824-945e-9719feda2f42"
/dev/sdm1: UUID="75515f3b-95ea-ef00-e327-c48e2784e416" UUID_SUB="52b46420-82ff-7e66-ff87-4195a846f804" LABEL="ubuntu:0" TYPE="linux_raid_member" PARTUUID="e02572d4-01"
/dev/sdn1: UUID="75515f3b-95ea-ef00-e327-c48e2784e416" UUID_SUB="5a61afd1-e3eb-d319-f6ca-a0135c0889de" LABEL="ubuntu:0" TYPE="linux_raid_member" PARTUUID="1e066523-01"
/dev/md0: UUID="42ba6b53-6752-4ca7-b5a7-95a5e766ce97" BLOCK_SIZE="4096" TYPE="ext4"
/dev/sdo: UUID="642af36d-7695-4376-a6f9-a35a15552e33" BLOCK_SIZE="4096" TYPE="ext4" """
        blkid_dict = Blkid.parse_blkid_output(input_blkid_string)

        os_prober_contents = """/dev/sdc2@/efi/Microsoft/Boot/bootmgfw.efi:Windows Boot Manager:Windows:efi
        /dev/sdd1:Debian GNU/Linux 10 (buster):Debian:linux"""
        osprober_dict = OsProber.parse_os_prober_output(os_prober_contents)

        input_parted_gpt_string = """Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sde: 2684354560B
Sector size (logical/physical): 512B/512B
Partition Table: gpt
Disk Flags: 

Number  Start        End          Size         File system  Name  Flags
 1      1048576B     114294783B   113246208B   ntfs               msftdata
 2      114294784B   181403647B   67108864B    fat32              msftdata
 3      181403648B   2458910719B  2277507072B  ntfs               msftdata
 4      2458910720B  2683305983B  224395264B   ext4"""
        parted_dict_dict['/dev/sde'] = Parted.parse_parted_output(input_parted_gpt_string)

        input_sfdisk_gpt_string = """label: gpt
label-id: 5FA01E95-F3E8-4B92-845B-843609E4EF0D
device: /dev/sde
unit: sectors
first-lba: 34
last-lba: 5242846

/dev/sde1 : start=        2048, size=      221184, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=4C6EC2CF-8DE5-43C0-9757-41A596DE5486
/dev/sde2 : start=      223232, size=      131072, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=BE9F4179-560C-4BC9-8366-AE214F69A16E
/dev/sde3 : start=      354304, size=     4448256, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=363BDD4E-D6A1-42E6-A4DA-616CD3E46952
/dev/sde4 : start=     4802560, size=      438272, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=CED0279D-0096-4EBE-8425-4C6C9D46A4D2"""
        sfdict_dict_dict['/dev/sde'] = Sfdisk.parse_sfdisk_dump_output(input_sfdisk_gpt_string)

        input_parted_mbr_string = """Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdd: 2147483648B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags: 

Number  Start        End          Size         Type      File system  Flags
 4      1048576B     2100297727B  2099249152B  extended
14      2097152B     47185919B    45088768B    logical   ext4
13      48234496B    77594623B    29360128B    logical   ext4
 5      78643200B    91226111B    12582912B    logical   ext4
 9      92274688B    113246207B   20971520B    logical   ext4
 6      114294784B   118489087B   4194304B     logical   ext2
 7      119537664B   147849215B   28311552B    logical   ext4
 8      148897792B   153092095B   4194304B     logical   ext2
10      154140672B   238026751B   83886080B    logical   ext4
11      239075328B   311427071B   72351744B    logical   ext4
12      312475648B   331350015B   18874368B    logical   ext4
 1      2100297728B  2103443455B  3145728B     primary   ext2
 2      2103443456B  2147483647B  44040192B    primary   ext4"""
        parted_dict_dict['/dev/sdd'] = Parted.parse_parted_output(input_parted_mbr_string)

        input_parted_sdm_string = """Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdm: 1073741824B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags:

Number  Start     End          Size         Type     File system  Flags
 1      1048576B  1073741823B  1072693248B  primary               raid

"""
        parted_dict_dict['/dev/sdm'] = Parted.parse_parted_output(input_parted_sdm_string)

        input_parted_sdn_string = """
Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdn: 1073741824B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags:

Number  Start     End          Size         Type     File system  Flags
 1      1048576B  1073741823B  1072693248B  primary               raid

"""
        parted_dict_dict['/dev/sdn'] = Parted.parse_parted_output(input_parted_sdn_string)

        input_parted_fs_directly_on_disk_string = """
Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdo: 1610612736B
Sector size (logical/physical): 512B/512B
Partition Table: loop
Disk Flags:

Number  Start  End          Size         File system  Flags
 1      0B     1610612735B  1610612736B  ext4

"""
        parted_dict_dict['/dev/sdo'] = Parted.parse_parted_output(input_parted_fs_directly_on_disk_string)

        input_sfdisk_sdm_string = """label: dos
label-id: 0xe02572d4
device: /dev/sdm
unit: sectors
sector-size: 512

/dev/sdm1 : start=        2048, size=     2095104, type=fd"""
        sfdict_dict_dict['/dev/sdm'] = Sfdisk.parse_sfdisk_dump_output(input_sfdisk_sdm_string)

        input_sfdisk_sdn_string = """label: dos
label-id: 0x1e066523
device: /dev/sdn
unit: sectors
sector-size: 512

/dev/sdn1 : start=        2048, size=     2095104, type=fd"""
        sfdict_dict_dict['/dev/sdn'] = Sfdisk.parse_sfdisk_dump_output(input_sfdisk_sdn_string)

        input_sfdisk_mbr_string = """label: dos
label-id: 0x1dbd2bfc
device: /dev/sdd
unit: sectors

/dev/sdd1 : start=     4102144, size=        6144, type=83
/dev/sdd2 : start=     4108288, size=       86016, type=83
/dev/sdd4 : start=        2048, size=     4100096, type=5
/dev/sdd5 : start=      153600, size=       24576, type=83
/dev/sdd6 : start=      223232, size=        8192, type=83
/dev/sdd7 : start=      233472, size=       55296, type=83
/dev/sdd8 : start=      290816, size=        8192, type=83
/dev/sdd9 : start=      180224, size=       40960, type=83
/dev/sdd10 : start=      301056, size=      163840, type=83
/dev/sdd11 : start=      466944, size=      141312, type=83
/dev/sdd12 : start=      610304, size=       36864, type=83
/dev/sdd13 : start=       94208, size=       57344, type=83
/dev/sdd14 : start=        4096, size=       88064, type=83 """
        sfdict_dict_dict['/dev/sdd'] = Sfdisk.parse_sfdisk_dump_output(input_sfdisk_mbr_string)
        pp = pprint.PrettyPrinter(indent=4)
        #combined_drive_state_dict = CombinedDriveState.construct_combined_drive_state_dict(lsblk_json_dict, blkid_dict, osprober_dict, parted_dict_dict, sfdict_dict_dict)
        #pp.pprint(combined_drive_state_dict)
        #CombinedDriveState.get_first_partition(combined_drive_state_dict['/dev/sdd']['partitions'])

        #expected_combined_drive_state_dict = {}
        #self.assertDictEqual(expected_combined_drive_state_dict, combined_drive_state_dict)
