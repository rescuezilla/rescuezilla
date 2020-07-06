# ----------------------------------------------------------------------
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

from parser.clonezilla_image import ClonezillaImage


class ClonezillaImageParsingTest(unittest.TestCase):
    def test_clonezilla_image(self):
        image = ClonezillaImage("/mnt/backup/clonezilla.focal/2020-08-30-15-img_mbr_many_different_fs/clonezilla-img")
        # assert_true("message", False)
        # assert_false("message", True)
        image = ClonezillaImage("/mnt/backup/clonezilla.focal/2020-09-02-07-img_ntfsclone_partimage/clonezilla-img")

        # sdf2.aa : Partimage
        # sdf6.ntfs-img.aa : NTFS Clone
        # sdf13.ext4-ptcl-img.gz.aa : Partclone ext4
        # sdf13.dd-ptcl-img.gz.aa : Partclone dd (same as regular dd data, it would appear)
        print("looking at " + str(image.dev_fs_dict))


    def test_dev_fs_list_parsing(self):
        dev_fs_list_string = """# This is a comment line
# Another comment line
/dev/sda3 ntfs
/dev/sda7 ext4
"""
        dev_fs_dict = ClonezillaImage.parse_dev_fs_list_output(dev_fs_list_string)
        expected_dict = {"/dev/sda3": "ntfs", "/dev/sda7": "ext4"}
        self.assertEqual(dev_fs_dict, expected_dict)

    def test_compression_detection(self):
        self.assertEqual("gzip", ClonezillaImage.extract_image_compression_from_file_utility("sdf1.dd-ptcl-img.gz.aa: gzip compressed data, max speed, from Unix, original size modulo 2^32 268435456 gzip compressed data, reserved method, from FAT filesystem (MS-DOS, OS/2, NT), original size modulo 2^32 268435456"))
        self.assertEqual("bzip2", ClonezillaImage.extract_image_compression_from_file_utility("sdd1.ext4-ptcl-img.bz2.aa: bzip2 compressed data, block size = 300k"))
        self.assertEqual("lzo", ClonezillaImage.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lzo.aa: lzop compressed data - version 1.040, LZO1X-1, os: Unix"))
        self.assertEqual("lzma", ClonezillaImage.extract_image_compression_from_file_utility("sdd1.ext4-ptcl-img.lzma.aa: LZMA compressed data, streamed"))
        self.assertEqual("xz", ClonezillaImage.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.xz.aa: XZ compressed data:"))
        self.assertEqual("lzip", ClonezillaImage.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lzip.aa: lzip compressed data, version: 1"))
        self.assertEqual("lrzip", ClonezillaImage.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lrz.aa: LRZIP compressed data - version 0.6"))
        self.assertEqual("lz4", ClonezillaImage.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.lz4.aa: LZ4 compressed data (v1.4+)"))
        self.assertEqual("zstd", ClonezillaImage.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.zst.aa: Zstandard compressed data (v0.8+), Dictionary ID: None"))
        self.assertEqual("uncompressed", ClonezillaImage.extract_image_compression_from_file_utility("sdb1.ext4-ptcl-img.uncomp.aa: data"))
