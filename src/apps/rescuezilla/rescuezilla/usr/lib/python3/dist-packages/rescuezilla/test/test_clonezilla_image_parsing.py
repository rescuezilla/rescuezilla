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

from parser.clonezilla_image import ClonezillaImage
from utility import Utility


class ClonezillaImageParsingTest(unittest.TestCase):
    def test_chs_sf_parsing(self):
        chs_sf_string = """cylinders=12336
heads=255
sectors=2"""
        chs_sf_dict = ClonezillaImage.parse_chs_sf_output(chs_sf_string)
        expected_dict = {'cylinders': 12336, 'heads': 255, 'sectors': 2}
        self.assertEqual(chs_sf_dict, expected_dict)

    def test_dev_fs_list_parsing(self):
        dev_fs_list_string = """# This is a comment line
# Another comment line
/dev/sda3 ntfs
/dev/sda7 ext4
"""
        dev_fs_dict = ClonezillaImage.parse_dev_fs_list_output(dev_fs_list_string)
        expected_dict = {'/dev/sda3': {'filesystem': "ntfs"}, '/dev/sda7': {'filesystem': "ext4"}}
        self.assertEqual(dev_fs_dict, expected_dict)

    # New dev-fs.list format since October 2020: https://github.com/rescuezilla/rescuezilla/issues/139
    def test_new_dev_fs_list_parsing(self):
        dev_fs_list_string = """# <Device name>   <File system>   <Size>
# File system is got from ocs-get-part-info. It might be different from that of blkid or parted.
/dev/sda1 vfat 512M
/dev/sda3 swap 15.9G"""
        dev_fs_dict = ClonezillaImage.parse_dev_fs_list_output(dev_fs_list_string)
        expected_dict = {'/dev/sda1': {'filesystem': "vfat", 'size': "512M"}, '/dev/sda3': {'filesystem': "swap", 'size': "15.9G"}}
        self.assertEqual(dev_fs_dict, expected_dict)

    def test_compression_detection(self):
        self.assertEqual("gzip", Utility.extract_image_compression_from_file_utility("sdf1.dd-ptcl-img.gz.aa: gzip compressed data, max speed, from Unix, original size modulo 2^32 268435456 gzip compressed data, reserved method, from FAT filesystem (MS-DOS, OS/2, NT), original size modulo 2^32 268435456"))
        self.assertEqual("bzip2", Utility.extract_image_compression_from_file_utility("sdd1.ext4-ptcl-img.bz2.aa: bzip2 compressed data, block size = 300k"))
        self.assertEqual("lzo", Utility.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lzo.aa: lzop compressed data - version 1.040, LZO1X-1, os: Unix"))
        self.assertEqual("lzma", Utility.extract_image_compression_from_file_utility("sdd1.ext4-ptcl-img.lzma.aa: LZMA compressed data, streamed"))
        self.assertEqual("xz", Utility.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.xz.aa: XZ compressed data:"))
        self.assertEqual("lzip", Utility.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lzip.aa: lzip compressed data, version: 1"))
        self.assertEqual("lrzip", Utility.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lrz.aa: LRZIP compressed data - version 0.6"))
        self.assertEqual("lz4", Utility.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lz4.aa: LZ4 compressed data (v1.4+)"))
        self.assertEqual("zstd", Utility.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.zst.aa: Zstandard compressed data (v0.8+), Dictionary ID: None"))
        self.assertEqual("uncompressed", Utility.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.uncomp.aa: data"))
