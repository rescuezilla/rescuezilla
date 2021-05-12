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
import pprint
import unittest

from parser.ecryptfs import Ecryptfs


class EcryptfsTest(unittest.TestCase):
    def test_ecryptfs_info_parsing(self):
        input_ecryptfs_info_string = """# This image was saved with ecryptfs
disk_of_img="sdf"
parts_of_img="sdf1 sdf2 sdf5 sdf6 sdf7 sdf8 sdf9 sdf10 sdf12 sdf13 sdf14 sdf15 sdf16 sdf17 sdf18 sdf19 sdf20"
time_of_img="2020-0910-1046"
disks_size_all_of_img="_3221MB" """
        ecryptfs_info_dict = Ecryptfs.parse_ecryptfs_info(input_ecryptfs_info_string)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(ecryptfs_info_dict)
        expected_ecryptfs_info_dict = {
            'disk': ["sdf"],
            'parts': ["sdf1", "sdf2", "sdf5", "sdf6", "sdf7", "sdf8", "sdf9", "sdf10", "sdf12", "sdf13", "sdf14", "sdf15", "sdf16", "sdf17", "sdf18", "sdf19", "sdf20"],
            "time": "2020-0910-1046",
            "size": "_3221MB"
        }

        self.assertDictEqual(expected_ecryptfs_info_dict, ecryptfs_info_dict)
