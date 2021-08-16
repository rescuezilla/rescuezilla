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
import collections
import unittest

from parser.lsblk import Lsblk


class LsblkTest(unittest.TestCase):
    def test_lsblk_json_parsing(self):
        # The output of `sudo lsblk -o KNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL --paths --bytes --json` is superior
        # to what is used by the Clonezilla format in the unit test below:
        #
        # --json provides data in JSON, which is trivially and reliably parsable in Python dict.
        # --bytes provides the exact size in bytes
        # --paths provides absolute device node paths for 'kname' and 'name' fields, useful for device mapper nodes.
        input_lsblk_json_string = """{
       "blockdevices": [
          {"kname":"/dev/loop0", "name":"/dev/loop0", "size":695181312, "type":"loop", "fstype":"squashfs", "mountpoint":"/rofs", "model":null},
          {"kname":"/dev/sda", "name":"/dev/sda", "size":34359738368, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK"},
          {"kname":"/dev/sdb", "name":"/dev/sdb", "size":1073741824, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK"},
          {"kname":"/dev/sdc", "name":"/dev/sdc", "size":2147483648, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
             "children": [
                {"kname":"/dev/sdc1", "name":"/dev/sdc1", "size":63963136, "type":"part", "fstype":"ext4", "mountpoint":null, "model":null},
                {"kname":"/dev/sdc2", "name":"/dev/sdc2", "size":120586240, "type":"part", "fstype":"vfat", "mountpoint":null, "model":null},
                {"kname":"/dev/sdc3", "name":"/dev/sdc3", "size":121634816, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null},
                {"kname":"/dev/sdc4", "name":"/dev/sdc4", "size":33554432, "type":"part", "fstype":"xfs", "mountpoint":null, "model":null},
                {"kname":"/dev/sdc5", "name":"/dev/sdc5", "size":199229440, "type":"part", "fstype":"reiser4", "mountpoint":null, "model":null},
                {"kname":"/dev/sdc6", "name":"/dev/sdc6", "size":48234496, "type":"part", "fstype":"hfsplus", "mountpoint":null, "model":null},
                {"kname":"/dev/sdc7", "name":"/dev/sdc7", "size":34603008, "type":"part", "fstype":"swap", "mountpoint":null, "model":null},
                {"kname":"/dev/sdc8", "name":"/dev/sdc8", "size":1523580928, "type":"part", "fstype":"ntfs", "mountpoint":null, "model":null}
             ]
          },
          {"kname":"/dev/sdd", "name":"/dev/sdd", "size":3221225472, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK"},
          {"kname":"/dev/sde", "name":"/dev/sde", "size":8589934592, "type":"disk", "fstype":null, "mountpoint":null, "model":"VBOX_HARDDISK",
             "children": [
                {"kname":"/dev/sde1", "name":"/dev/sde1", "size":536870912, "type":"part", "fstype":"vfat", "mountpoint":null, "model":null},
                {"kname":"/dev/sde2", "name":"/dev/sde2", "size":255852544, "type":"part", "fstype":"ext2", "mountpoint":null, "model":null},
                {"kname":"/dev/sde3", "name":"/dev/sde3", "size":7795113984, "type":"part", "fstype":"crypto_LUKS", "mountpoint":null, "model":null}
             ]
          },
          {"kname":"/dev/sr0", "name":"/dev/sr0", "size":801519616, "type":"rom", "fstype":"iso9660", "mountpoint":"/cdrom", "model":"VBOX_CD-ROM"}
       ]
    }
    """
        lsblk_dict = Lsblk.parse_lsblk_json_output(input_lsblk_json_string)
        #pp = pprint.PrettyPrinter(indent=4)
        #pp.pprint(lsblk_dict)

    def test_lsblk_parsing(self):
        # Output of: lsblk -o KNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL
        # Used by Clonezilla, but Rescuezilla uses the JSON approach above.
        input_lsblk_string = """KNAME NAME     SIZE TYPE FSTYPE      MOUNTPOINT MODEL
loop0 loop0    663M loop squashfs    /rofs
sda   sda       32G disk                        VBOX_HARDDISK
sdb   sdb        1G disk                        VBOX_HARDDISK
sdc   sdc        2G disk                        VBOX_HARDDISK
sdc1  ├─sdc1    61M part ext4
sdc2  ├─sdc2   115M part vfat
sdc3  ├─sdc3   116M part ntfs
sdc4  ├─sdc4    32M part xfs
sdc5  ├─sdc5   190M part reiser4
sdc6  ├─sdc6    46M part hfsplus
sdc7  ├─sdc7    33M part swap
sdc8  └─sdc8   1.4G part ntfs
sdd   sdd        3G disk                        VBOX_HARDDISK
sde   sde        8G disk                        VBOX_HARDDISK
sde1  ├─sde1   512M part vfat
sde2  ├─sde2   244M part ext2
sde3  └─sde3   7.3G part crypto_LUKS
sr0   sr0    764.4M rom  iso9660     /cdrom     VBOX_CD-ROM"""
        lsblk_dict = Lsblk.parse_lsblk_output(input_lsblk_string)
        expected_lsblk_dict = collections.OrderedDict([('loop0', {'kname': 'loop0', 'size': '663M', 'type': 'loop', 'fstype': 'squashfs', 'mountpoint': '/rofs', 'model': ''}),
                                                       ('sda', {'kname': 'sda', 'size': '32G', 'type': 'disk', 'fstype': '', 'mountpoint': '', 'model': 'VBOX_HARDDISK'}),
                                                       ('sdb', {'kname': 'sdb', 'size': '1G', 'type': 'disk', 'fstype': '', 'mountpoint': '', 'model': 'VBOX_HARDDISK'}),
                                                       ('sdc', {'kname': 'sdc', 'size': '2G', 'type': 'disk', 'fstype': '', 'mountpoint': '', 'model': 'VBOX_HARDDISK'}),
                                                       ('sdc1', {'kname': 'sdc1', 'size': '61M', 'type': 'part', 'fstype': 'ext4', 'mountpoint': '', 'model': ''}),
                                                       ('sdc2', {'kname': 'sdc2', 'size': '115M', 'type': 'part', 'fstype': 'vfat', 'mountpoint': '', 'model': ''}),
                                                       ('sdc3', {'kname': 'sdc3', 'size': '116M', 'type': 'part', 'fstype': 'ntfs', 'mountpoint': '', 'model': ''}),
                                                       ('sdc4', {'kname': 'sdc4', 'size': '32M', 'type': 'part', 'fstype': 'xfs', 'mountpoint': '', 'model': ''}),
                                                       ('sdc5', {'kname': 'sdc5', 'size': '190M', 'type': 'part', 'fstype': 'reiser4', 'mountpoint': '', 'model': ''}),
                                                       ('sdc6', {'kname': 'sdc6', 'size': '46M', 'type': 'part', 'fstype': 'hfsplus', 'mountpoint': '', 'model': ''}),
                                                       ('sdc7', {'kname': 'sdc7', 'size': '33M', 'type': 'part', 'fstype': 'swap', 'mountpoint': '', 'model': ''}),
                                                       ('sdc8', {'kname': 'sdc8', 'size': '1.4G', 'type': 'part', 'fstype': 'ntfs', 'mountpoint': '', 'model': ''}),
                                                       ('sdd', {'kname': 'sdd', 'size': '3G', 'type': 'disk', 'fstype': '', 'mountpoint': '', 'model': 'VBOX_HARDDISK'}),
                                                       ('sde', {'kname': 'sde', 'size': '8G', 'type': 'disk', 'fstype': '', 'mountpoint': '', 'model': 'VBOX_HARDDISK'}),
                                                       ('sde1', {'kname': 'sde1', 'size': '512M', 'type': 'part', 'fstype': 'vfat', 'mountpoint': '', 'model': ''}),
                                                       ('sde2', {'kname': 'sde2', 'size': '244M', 'type': 'part', 'fstype': 'ext2', 'mountpoint': '', 'model': ''}),
                                                       ('sde3', {'kname': 'sde3', 'size': '7.3G', 'type': 'part', 'fstype': 'crypto_LUKS', 'mountpoint': '', 'model': ''}),
                                                       ('sr0', {'kname': 'sr0', 'size': '764.4M', 'type': 'rom', 'fstype': 'iso9660', 'mountpoint': '/cdrom', 'model': 'VBOX_CD-ROM'})])

        self.assertDictEqual(expected_lsblk_dict, lsblk_dict)
