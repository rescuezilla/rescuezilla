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

from parser.parted import Parted


class PartedTest(unittest.TestCase):
    def test_parted_gpt_parsing(self):
        # Output of: parted -s /dev/sdc unit B print
        input_parted_gpt_string = """Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdc: 2147483648B
Sector size (logical/physical): 512B/512B
Partition Table: gpt
Disk Flags:

Number  Start       End          Size         File system     Name  Flags
 1      1048576B    65011711B    63963136B    ext4
 2      65011712B   185597951B   120586240B   fat32                 msftdata
 3      185597952B  307232767B   121634816B   ntfs                  msftdata
 4      307232768B  340787199B   33554432B    xfs
 5      340787200B  540016639B   199229440B
 6      540016640B  588251135B   48234496B    hfs+
 7      588251136B  622854143B   34603008B    linux-swap(v1)        swap
 8      622854144B  2146435071B  1523580928B  ntfs                  msftdata
"""

        parted_dict = Parted.parse_parted_output(input_parted_gpt_string)
        print("Output dict was: " + str(parted_dict))
        self.assertEqual(parted_dict['model'], "ATA VBOX HARDDISK (scsi)")
        self.assertEqual(parted_dict['long_dev_node'], "/dev/sdc")
        self.assertEqual(parted_dict['capacity'], 2147483648)
        self.assertEqual(parted_dict['logical_sector_size'], 512)
        self.assertEqual(parted_dict['physical_sector_size'], 512)
        self.assertEqual(parted_dict['partition_table'], "gpt")
        self.assertEqual(parted_dict['flags'], "")

        self.assertEqual(len(parted_dict['partitions']), 8)

        partition1 = parted_dict['partitions'][1]
        self.assertEqual(partition1['start'], 1048576)
        self.assertEqual(partition1['end'], 65011711)
        self.assertEqual(partition1['size'], 63963136)
        self.assertEqual(partition1['filesystem'], "ext4")
        self.assertEqual(partition1['name'], "")
        self.assertEqual(partition1['flags'], "")

        partition7 = parted_dict['partitions'][6]
        self.assertEqual(partition7['filesystem'], "hfs+")

        partition7 = parted_dict['partitions'][7]
        self.assertEqual(partition7['filesystem'], "linux-swap(v1)")
        self.assertEqual(partition7['flags'], "swap")

    def test_parted_mbr_parsing(self):
        # Output of: parted -s /dev/sdc unit B print
        input_parted_mbr_string = """Model: ATA VBOX HARDDISK (scsi)
Disk /dev/sdc: 2147483648B
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags:

Number  Start       End          Size         Type      File system     Flags
 1      1048576B    91226111B    90177536B    primary   ext4
 2      91226112B   185597951B   94371840B    primary   ntfs
 3      185597952B  338690047B   153092096B   primary   fat32
 4      338690048B  2147483647B  1808793600B  extended
 5      339738624B  350224383B   10485760B    logical   linux-swap(v1)
 6      351272960B  419430399B   68157440B    logical
 7      420478976B  688914431B   268435456B   logical   btrfs
 8      689963008B  723517439B   33554432B    logical   xfs
 9      724566016B  2147483647B  1422917632B  logical   ntfs
"""
        parted_dict = Parted.parse_parted_output(input_parted_mbr_string)
        print("Output dict was: " + str(parted_dict))
        self.assertEqual(parted_dict['model'], "ATA VBOX HARDDISK (scsi)")
        self.assertEqual(parted_dict['long_dev_node'], "/dev/sdc")
        self.assertEqual(parted_dict['capacity'], 2147483648)
        self.assertEqual(parted_dict['logical_sector_size'], 512)
        self.assertEqual(parted_dict['logical_sector_size'], 512)
        self.assertEqual(parted_dict['physical_sector_size'], 512)
        self.assertEqual(parted_dict['partition_table'], "msdos")
        self.assertEqual(parted_dict['flags'], "")

        self.assertEqual(len(parted_dict['partitions']), 9)

        self.assertEqual(parted_dict['partitions'][3]['type'], "primary")
        self.assertEqual(parted_dict['partitions'][4]['type'], "extended")
        self.assertEqual(parted_dict['partitions'][5]['type'], "logical")

        partition9 = parted_dict['partitions'][9]
        self.assertEqual(partition9['start'], 724566016)
        self.assertEqual(partition9['end'], 2147483647)
        self.assertEqual(partition9['size'], 1422917632)
        self.assertEqual(partition9['type'], "logical")
        self.assertEqual(partition9['filesystem'], "ntfs")
        self.assertEqual(partition9['flags'], "")

    def test_parted_no_partitions_in_sectors_parsing(self):
        input_parted_string = """Model: Mock up test
Disk /dev/sdc: 123s
Sector size (logical/physical): 512s/512s
Partition Table: unknown
Disk Flags:
"""
        parted_dict = Parted.parse_parted_output(input_parted_string)
        print("Output dict was: " + str(parted_dict))

    def test_flag_detection(self):
        # Modified input string to add "bios_grub" to flag section
        input_parted_gpt_string = """Model: Testing a certain flag
Disk /dev/sdc: 2147483648B
Sector size (logical/physical): 512B/512B
Partition Table: gpt
Disk Flags:

Number  Start       End          Size         File system     Name  Flags
 1      1048576B    65011711B    63963136B    ext4
 2      65011712B   185597951B   120586240B   fat32                 test,bios_grub
 3      185597952B  307232767B   121634816B   ntfs                  test,msftdata,boot
"""

        parted_dict = Parted.parse_parted_output(input_parted_gpt_string)
        self.assertEqual(Parted.get_partitions_containing_flag(parted_dict, "bios_grub"), [2])
        self.assertEqual(Parted.get_partitions_containing_flag(parted_dict, "boot"), [3])
        self.assertEqual(Parted.get_partitions_containing_flag(parted_dict, "test"), [2,3])
        parted_dict['partitions'][2]['flags'] = "asdf"
        self.assertFalse(Parted.get_partitions_containing_flag(parted_dict, "bios_grub"), [])
        parted_dict['partitions'][2]['flags'] = "msftdata,bios_grub"
        self.assertTrue(Parted.get_partitions_containing_flag(parted_dict, "bios_grub"), [3])
