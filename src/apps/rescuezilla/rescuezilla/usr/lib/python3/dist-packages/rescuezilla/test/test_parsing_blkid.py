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
import unittest

from parser.blkid import Blkid


class BlkidTest(unittest.TestCase):
    def test_blkid_parsing(self):
        # Output of: `blkid` (with no arguments)
        input_blkid_string = """/dev/sda1: UUID="0354526A55E7267A" TYPE="ntfs" PTTYPE="dos" PARTUUID="80827ac0-298e-438c-8854-42aab5e1954c"
/dev/sdc1: UUID="4f3cab4f-2a7d-43e5-9219-de7bb94b5b2e" TYPE="ext4" PARTUUID="0ac0b05d-406e-4995-b032-1776ad0a87e3"
/dev/sdc2: UUID="5176-0026" TYPE="vfat" PARTUUID="497ab23e-3566-4544-8659-c1210dafb621"
/dev/sdc3: UUID="50FD7236021DBC16" TYPE="ntfs" PTTYPE="dos" PARTUUID="161458e9-eafc-4b18-ab8d-56152b29b8b5"
/dev/sdc6: UUID="aac8f01a-ba7c-3c71-9267-86ae94bf39b9" LABEL="untitled" TYPE="hfsplus" PARTUUID="1d0cf486-b483-4d30-b0c3-60cd4d71f66d"
/dev/sdc8: UUID="14FC1B2B3D69E002" TYPE="ntfs" PTTYPE="dos" PARTUUID="ada38fe6-687c-4cd9-8fa3-6abd9e1a3d81"
/dev/sr0: UUID="2020-06-26-05-33-51-00" LABEL="Rescuezilla" TYPE="iso9660" PTTYPE="PMBR"
/dev/loop0: TYPE="squashfs" PARTLABEL="This string has spaces" LABEL="Another label"
/dev/sdc4: UUID="fc93c6bf-6e02-4150-be08-6ad1d61ac2ed" TYPE="xfs" PARTUUID="15121dd7-3e30-4d0d-b545-af39901e36fd"
/dev/sdc5: UUID="b49c36be-6549-4d52-bacf-1172ae0946ac" TYPE="reiser4" PARTUUID="2fa17c84-a52f-4d46-9096-e733807c4862"
/dev/sdc7: UUID="988916bb-dfa9-456b-9c03-ec85a60b2054" TYPE="swap" PARTUUID="bf532c13-b749-4491-98ff-3a26e87025d1"
"""
        blkid_dict = Blkid.parse_blkid_output(input_blkid_string)
        expected_blkid_dict = {
            '/dev/sda1': {
                'UUID': "0354526A55E7267A",
                'TYPE': "ntfs",
                'PTTYPE': "dos",
                'PARTUUID': "80827ac0-298e-438c-8854-42aab5e1954c"
            },
            '/dev/sdc1': {
                'UUID': "4f3cab4f-2a7d-43e5-9219-de7bb94b5b2e",
                'TYPE': "ext4",
                'PARTUUID': "0ac0b05d-406e-4995-b032-1776ad0a87e3"
            },
            '/dev/sdc2': {
                'UUID': "5176-0026",
                'TYPE': "vfat",
                'PARTUUID': "497ab23e-3566-4544-8659-c1210dafb621"
            },
            '/dev/sdc3': {
                'UUID': "50FD7236021DBC16",
                'TYPE': "ntfs",
                'PTTYPE': "dos",
                'PARTUUID': "161458e9-eafc-4b18-ab8d-56152b29b8b5"
            },
            '/dev/sdc6': {
                'UUID': "aac8f01a-ba7c-3c71-9267-86ae94bf39b9",
                'LABEL': "untitled",
                'TYPE': "hfsplus",
                'PARTUUID': "1d0cf486-b483-4d30-b0c3-60cd4d71f66d"
            },
            '/dev/sdc8': {
                'UUID': "14FC1B2B3D69E002",
                'TYPE': "ntfs",
                'PTTYPE': "dos",
                'PARTUUID': "ada38fe6-687c-4cd9-8fa3-6abd9e1a3d81"
            },
            '/dev/sr0': {
                'UUID': "2020-06-26-05-33-51-00",
                'LABEL': "Rescuezilla",
                'TYPE': "iso9660",
                'PTTYPE': "PMBR"
            },
            '/dev/loop0': {
                'TYPE': "squashfs",
                'PARTLABEL': "This string has spaces",
                'LABEL': "Another label",
            },
            '/dev/sdc4': {
                'UUID': "fc93c6bf-6e02-4150-be08-6ad1d61ac2ed",
                'TYPE': "xfs",
                'PARTUUID': "15121dd7-3e30-4d0d-b545-af39901e36fd"
            },
            '/dev/sdc5': {
                'UUID': "b49c36be-6549-4d52-bacf-1172ae0946ac",
                'TYPE': "reiser4",
                'PARTUUID': "2fa17c84-a52f-4d46-9096-e733807c4862"
            },
            '/dev/sdc7': {
                'UUID': "988916bb-dfa9-456b-9c03-ec85a60b2054",
                'TYPE': "swap",
                'PARTUUID': "bf532c13-b749-4491-98ff-3a26e87025d1"
            }
        }
        self.assertDictEqual(expected_blkid_dict, blkid_dict)
