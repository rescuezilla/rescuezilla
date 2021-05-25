# ----------------------------------------------------------------------
#   Copyright (C) 2003-2021 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2021-2021 Rescuezilla.com <rescuezilla@gmail.com>
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

from parser.proc_mdstat import ProcMdstat


class ProcMdstatTest(unittest.TestCase):
    def test_get_active_raid_devices(self):
        input_proc_mdstat_string = """Personalities : [raid1] [raid0] [linear] [multipath] [raid6] [raid5] [raid4] [raid10]
md125 : active (auto-read-only) raid1 sdb1[1] sda1[0]
      499968 blocks super 1.0 [2/2] [UU]
      bitmap: 0/1 pages [0KB], 65536KB chunk

md126 : active raid0 sda3[0] sdb3[1]
      15761408 blocks super 1.2 512k chunks

md127 : active (auto-read-only) raid1 sda2[0] sdb2[1]
      12573696 blocks super 1.2 [2/2] [UU]
      bitmap: 0/1 pages [0KB], 65536KB chunk"""

        proc_mdstat_dict = ProcMdstat.parse_proc_mdstat_string(input_proc_mdstat_string)
        actual_mdstat_device_list = list(proc_mdstat_dict.keys())
        expected = ["md125", "md126", "md127"]
        self.assertEqual(expected, actual_mdstat_device_list)
