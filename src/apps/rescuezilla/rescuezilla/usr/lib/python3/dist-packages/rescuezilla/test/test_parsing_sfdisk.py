# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
#   Copyright (C) 2003-2020 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2019-2020 Rescuezilla.com <rescuezilla@gmail.com>
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

from parser.sfdisk import Sfdisk


class SfdiskTest(unittest.TestCase):
    def test_sfdisk_parsing(self):
        # Output of: sfdisk -l /dev/sdb
        # --dumps vs --list
        input_sfdisk_string = """label: gpt
label-id: 20B6B2AC-F20E-48A7-83C5-6B684328AFAB
device: /dev/sdb
unit: sectors
first-lba: 34
last-lba: 16223214

/dev/sdb1 : start=        2048, size=     1849344, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, uuid=ABEC187C-BD81-4F2F-B8C0-0DB4892055E2
/dev/sdb2 : start=     1851392, size=     1351680, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=9A0ECA81-6D1A-497E-8614-B70404C37918
/dev/sdb3 : start=     3203072, size=    13019136, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=B65EDC17-2C20-46B0-BD65-C92167FFEEC2
"""
        sfdisk_dict = Sfdisk.parse_sfdisk_dump_output(input_sfdisk_string)
        expected_sfdisk_dict = {
            'label': 'gpt',
            'label-id': '20B6B2AC-F20E-48A7-83C5-6B684328AFAB',
            'device': '/dev/sdb',
            'first-lba': 34,
            'last-lba': 16223214,
            'partitions': {
                '/dev/sdb1': {
                    'start': 2048,
                    'size': 1849344,
                    'type': '0FC63DAF-8483-4772-8E79-3D69D8477DE4',
                    'uuid': 'ABEC187C-BD81-4F2F-B8C0-0DB4892055E2'
                },
                '/dev/sdb2': {
                    'start': 1851392,
                    'size': 1351680,
                    'type': 'EBD0A0A2-B9E5-4433-87C0-68B6B72699C7',
                    'uuid': '9A0ECA81-6D1A-497E-8614-B70404C37918'
                },
                '/dev/sdb3': {
                    'start': 3203072,
                    'size': 13019136,
                    'type': 'EBD0A0A2-B9E5-4433-87C0-68B6B72699C7',
                    'uuid': 'B65EDC17-2C20-46B0-BD65-C92167FFEEC2'
                }
            }
        }
        print("actual:" + str(sfdisk_dict))
        #self.assertDictEqual(expected_sfdisk_dict, sfdisk_dict)

    def test_geometry_parsing(self):
        input_sfdisk_geometry = "/dev/sda: 12345 cylinders, 255 heads, 63 sectors/track"
        geometry_dict = Sfdisk.parse_sfdisk_show_geometry(input_sfdisk_geometry)

        expected_geometry_dict = {
            'cylinders': 12345,
            'heads': 255,
            'sectors': 63
        }
        self.assertDictEqual(expected_geometry_dict, geometry_dict)
