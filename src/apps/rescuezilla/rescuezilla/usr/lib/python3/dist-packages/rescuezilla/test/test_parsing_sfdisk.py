# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
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
import pprint
import unittest

from parser.sfdisk import Sfdisk


class SfdiskTest(unittest.TestCase):
    pp = pprint.PrettyPrinter(indent=4)

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

    def test_sfdisk_parsing_many_fields(self):
        input_sfdisk_string = """label: gpt
label-id: A9A88DF9-EA91-4E83-8616-0C1BB3BA28BA
device: /dev/sda
unit: sectors
first-lba: 34
last-lba: 104857566
sector-size: 512

/dev/sda1 : start=        2048, size=     1083392, type=DE94BBA4-06D1-4D40-A16A-BFD50179D6AC, uuid=E3E94AE6-C2AB-495A-A955-A32140F56C2A, name="Basic data partition", attrs="RequiredPartition GUID:63"
/dev/sda2 : start=     1085440, size=      204800, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, uuid=7423670F-D0C3-4724-82F7-3185350A1BF7, name="EFI system partition", attrs="GUID:63"
/dev/sda3 : start=     1290240, size=       32768, type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE, uuid=229EF65D-3315-4824-945E-9719FEDA2F42, name="Microsoft reserved partition", attrs="GUID:63"
/dev/sda4 : start=     1323008, size=   103532544, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, uuid=1F1C6171-D10C-44C0-BA9B-E12995D7F4DA, name="Basic data partition"""
        sfdisk_dict = Sfdisk.parse_sfdisk_dump_output(input_sfdisk_string)
        pprint.pprint(sfdisk_dict)

    def test_geometry_parsing(self):
        input_sfdisk_geometry = "/dev/sda: 12345 cylinders, 255 heads, 63 sectors/track"
        geometry_dict = Sfdisk.parse_sfdisk_show_geometry(input_sfdisk_geometry)

        expected_geometry_dict = {
            'cylinders': 12345,
            'heads': 255,
            'sectors': 63
        }
        self.assertDictEqual(expected_geometry_dict, geometry_dict)
