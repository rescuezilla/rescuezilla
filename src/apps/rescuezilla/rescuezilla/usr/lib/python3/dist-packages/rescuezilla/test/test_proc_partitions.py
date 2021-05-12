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

class ProcPartitionsTest(unittest.TestCase):
    def test_are_partitions_listed_in_proc_partitions(self):
        input_proc_partitions_string = """major minor  #blocks  name

 259        0          1 nvme1n1
 259        1         42 nvme1n1p1
   8        0        123 sda
   8        1        321 sda1
 254        0        987 dm-0
"""
        from parser.proc_partitions import ProcPartitions
        self.assertTrue(ProcPartitions.are_partitions_listed_in_proc_partitions(input_proc_partitions_string, "nvme1n1"))
        self.assertFalse(ProcPartitions.are_partitions_listed_in_proc_partitions(input_proc_partitions_string, "nvme2n1"))
        self.assertFalse(ProcPartitions.are_partitions_listed_in_proc_partitions(input_proc_partitions_string, "sda"))
        self.assertFalse(ProcPartitions.are_partitions_listed_in_proc_partitions(input_proc_partitions_string, "sda3"))
        self.assertFalse(ProcPartitions.are_partitions_listed_in_proc_partitions(input_proc_partitions_string, "sda1"))
