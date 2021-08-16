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
import unittest

from utility import Utility


class UtilityTest(unittest.TestCase):
    def split(self, split_string, expected_base_device_node, expected_partition_number):
        base_device_node, partition_number = Utility.split_device_string(split_string)
        self.assertEqual(expected_base_device_node, base_device_node)
        self.assertEqual(expected_partition_number, partition_number)

    def join(self, base_device_node, partition_number, expected_device_node):
        device_node = Utility.join_device_string(base_device_node, partition_number)
        self.assertEqual(expected_device_node, device_node)

    def test_split_join_nodes(self):
        self.split("/dev/hdc7", "hdc", 7)
        self.join("hdc", 7, "hdc7")
        self.split("/dev/hdc", "hdc", 0)
        self.join("hdc", 0, "hdc")
        self.split("/dev/sda4", "sda", 4)
        self.join("sda", 4, "sda4")
        self.split("/dev/sda", "sda", 0)
        self.join("sda", 0, "sda")
        self.split("/dev/vdf5", "vdf", 5)
        self.join("vdf", 5, "vdf5")
        self.split("/dev/vdf", "vdf", 0)
        self.join("vdf", 0, "vdf")
        self.split("/dev/xvdl6", "xvdl", 6)
        self.join("xvdl", 6, "xvdl6")
        self.split("/dev/xvdl", "xvdl", 0)
        self.join("xvdl", 0, "xvdl")
        self.split("/dev/nvme3n4p5", "nvme3n4", 5)
        self.join("nvme3n4", 5, "nvme3n4p5")
        self.split("/dev/nvme3n1", "nvme3n1", 0)
        self.join("nvme3n1", 0, "nvme3n1")
        self.split("/dev/mmcblk6p5", "mmcblk6", 5)
        self.join("mmcblk6", 5, "mmcblk6p5")
        self.split("/dev/loop3p4", "loop3", 4)
        self.join("loop3", 4, "loop3p4")
        self.split("/dev/loop3", "loop3", 0)
        self.join("loop3", 0, "loop3")
        self.split("/dev/md126p3", "md126", 3)
        self.join("md126", 3, "md126p3")
        self.split("/dev/md126", "md126", 0)
        self.join("md126", 0, "md126")

        # base_device_node, partition_number = Utility.split_device_string("/dev/mapper/lgtest1-lvtest1")
        # self.assertEquals("md126", base_device_node)
        # self.assertEquals(0, partition_number)
