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

from parser.partclone import Partclone


class PartcloneTest(unittest.TestCase):

    def test_partclone_restore_parsing_short(self):
        partclone_restore_example_contents = """Partclone v0.3.13 http://partclone.org
Starting to restore image (-) to device (/dev/sdh5)
Calculating bitmap... Please wait...
done!
File system:  EXTFS
Device size:   52.4 MB = 12800 Blocks
Space in use:   5.9 MB = 1437 Blocks
Free Space:    46.5 MB = 11363 Blocks
Block size:   4096 Byte

                                                                                
Elapsed: 00:00:02, Remaining: 00:00:00, Completed: 100.00%, Rate: 176.58MB/min,

                                                                                
current block:       1437, total block:      12800, Complete: 100.00%
Total Time: 00:00:02, Ave. Rate:  176.6MB/min, 100.00% completed!
Syncing... OK!
Partclone successfully restored the image (-) to the device (/dev/sdh5)
Cloned successfully."""
        for line in partclone_restore_example_contents.splitlines():
            partclone_dict = Partclone.parse_partclone_output(line)
            if len(partclone_dict) != 0:
                print(partclone_dict)

    def test_partclone_restore_parsing_long(self):
        partclone_example_contents = """
    Partclone v0.3.13 http://partclone.org
Starting to restore image (-) to device (/dev/sdc5)
Calculating bitmap... Please wait...
done!
File system:  NTFS
Device size:  983.6 MB = 240127 Blocks
Space in use:   5.4 MB = 1320 Blocks
Free Space:   978.2 MB = 238807 Blocks
Block size:   4096 Byte
                                                                               Elapsed: 00:00:01, Remaining: 00:01:39, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:02, Remaining: 00:03:18, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:04, Remaining: 00:06:36, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:06, Remaining: 00:09:54, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:08, Remaining: 00:13:12, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:10, Remaining: 00:16:30, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:12, Remaining: 00:19:48, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:14, Remaining: 00:23:06, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:16, Remaining: 00:26:24, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:18, Remaining: 00:29:42, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:20, Remaining: 00:33:00, Completed:   1.00%,   0.00byte/min,
                                                                               Elapsed: 00:00:22, Remaining: 00:01:31, Completed:  19.39%,   2.86MB/min,
                                                                               Elapsed: 00:00:24, Remaining: 00:01:39, Completed:  19.39%,   2.62MB/min,
                                                                               Elapsed: 00:00:26, Remaining: 00:01:48, Completed:  19.39%,   2.42MB/min,
                                                                               Elapsed: 00:00:28, Remaining: 00:01:56, Completed:  19.39%,   2.25MB/min,
                                                                               Elapsed: 00:00:30, Remaining: 00:02:04, Completed:  19.39%,   2.10MB/min,
                                                                               Elapsed: 00:00:32, Remaining: 00:02:13, Completed:  19.39%,   1.97MB/min,
                                                                               Elapsed: 00:00:34, Remaining: 00:02:21, Completed:  19.39%,   1.85MB/min,
                                                                               Elapsed: 00:00:36, Remaining: 00:02:29, Completed:  19.39%,   1.75MB/min,
                                                                               Elapsed: 00:00:38, Remaining: 00:02:37, Completed:  19.39%,   1.66MB/min,
                                                                               Elapsed: 00:00:40, Remaining: 00:02:46, Completed:  19.39%,   1.57MB/min,
                                                                               Elapsed: 00:00:42, Remaining: 00:01:06, Completed:  38.79%,   3.00MB/min,
                                                                               Elapsed: 00:00:44, Remaining: 00:01:09, Completed:  38.79%,   2.86MB/min,
                                                                               Elapsed: 00:00:46, Remaining: 00:01:12, Completed:  38.79%,   2.74MB/min,
                                                                               Elapsed: 00:00:48, Remaining: 00:01:15, Completed:  38.79%,   2.62MB/min,
                                                                               Elapsed: 00:00:50, Remaining: 00:01:18, Completed:  38.79%,   2.52MB/min,
                                                                               Elapsed: 00:00:52, Remaining: 00:01:22, Completed:  38.79%,   2.42MB/min,
                                                                               Elapsed: 00:00:54, Remaining: 00:01:25, Completed:  38.79%,   2.33MB/min,
                                                                               Elapsed: 00:00:56, Remaining: 00:01:28, Completed:  38.79%,   2.25MB/min,
                                                                               Elapsed: 00:00:58, Remaining: 00:01:31, Completed:  38.79%,   2.17MB/min,
                                                                               Elapsed: 00:01:00, Remaining: 00:01:34, Completed:  38.79%,   2.10MB/min,
                                                                               Elapsed: 00:01:02, Remaining: 00:00:44, Completed:  58.18%,   3.04MB/min,
                                                                               Elapsed: 00:01:04, Remaining: 00:00:46, Completed:  58.18%,   2.95MB/min,
                                                                               Elapsed: 00:01:06, Remaining: 00:00:47, Completed:  58.18%,   2.86MB/min,
                                                                               Elapsed: 00:01:08, Remaining: 00:00:48, Completed:  58.18%,   2.78MB/min,
                                                                               Elapsed: 00:01:10, Remaining: 00:00:50, Completed:  58.18%,   2.70MB/min,
                                                                               Elapsed: 00:01:12, Remaining: 00:00:51, Completed:  58.18%,   2.62MB/min,
                                                                               Elapsed: 00:01:14, Remaining: 00:00:53, Completed:  58.18%,   2.55MB/min,
                                                                               Elapsed: 00:01:16, Remaining: 00:00:54, Completed:  58.18%,   2.48MB/min,
                                                                               Elapsed: 00:01:18, Remaining: 00:00:56, Completed:  58.18%,   2.42MB/min,
                                                                               Elapsed: 00:01:20, Remaining: 00:00:57, Completed:  58.18%,   2.36MB/min,
                                                                               Elapsed: 00:01:22, Remaining: 00:00:23, Completed:  77.58%,   3.07MB/min,
                                                                               Elapsed: 00:01:24, Remaining: 00:00:24, Completed:  77.58%,   3.00MB/min,
                                                                               Elapsed: 00:01:26, Remaining: 00:00:24, Completed:  77.58%,   2.93MB/min,
                                                                               Elapsed: 00:01:28, Remaining: 00:00:25, Completed:  77.58%,   2.86MB/min,
                                                                               Elapsed: 00:01:30, Remaining: 00:00:26, Completed:  77.58%,   2.80MB/min,
                                                                               Elapsed: 00:01:32, Remaining: 00:00:26, Completed:  77.58%,   2.74MB/min,
                                                                               Elapsed: 00:01:34, Remaining: 00:00:27, Completed:  77.58%,   2.68MB/min,
                                                                               Elapsed: 00:01:36, Remaining: 00:00:27, Completed:  77.58%,   2.62MB/min,
                                                                               Elapsed: 00:01:38, Remaining: 00:00:28, Completed:  77.58%,   2.57MB/min,
                                                                               Elapsed: 00:01:40, Remaining: 00:00:28, Completed:  77.58%,   2.52MB/min,
                                                                               Elapsed: 00:01:42, Remaining: 00:00:29, Completed:  77.58%,   2.47MB/min,
                                                                               Elapsed: 00:01:44, Remaining: 00:00:03, Completed:  96.97%,   3.02MB/min,
                                                                               Elapsed: 00:01:46, Remaining: 00:00:00, Completed: 100.00%, Rate:   3.06MB/min
                                                                               current block:     121264, total block:     240127, Complete: 100.00%
Total Time: 00:01:46, Ave. Rate:    3.1MB/min, 100.00% completed!
Syncing... OK!
Partclone successfully restored the image (-) to the device (/dev/sdc5)
Cloned successfully.
"""
        for line in partclone_example_contents.splitlines():
            partclone_dict = Partclone.parse_partclone_output(line)
            if len(partclone_dict) != 0:
                print(partclone_dict)

    def test_partclone_info_parsing(self):
        partclone_info_output = """Partclone v0.3.13 http://partclone.org
Showing info of image (-)
File system:  NTFS
Device size:  113.2 MB = 27647 Blocks
Space in use:   2.6 MB = 625 Blocks
Free Space:   110.7 MB = 27022 Blocks
Block size:   4096 Byte

image format:    0001
created on a:    n/a
with partclone:  n/a
bitmap mode:     BYTE
checksum algo:   CRC32_0001
checksum size:   4
blocks/checksum: 1
reseed checksum: no
"""
        partclone_info_dict = Partclone.parse_partclone_info_output(partclone_info_output)
        expected_partclone_info_dict = {
            'filesystem': "NTFS",
            'size': {'enduser_readable': "113.2 MB", 'blocks': 27647, 'bytes': 113242112},
            'used_space': {'enduser_readable': "2.6 MB", 'blocks': 625, 'bytes': 2560000},
            'free_space': {'enduser_readable': "110.7 MB", 'blocks': 27022, 'bytes': 110682112},
            'block_size': 4096,
            'image_format': "0001",
            "created": "n/a",
            "with_partclone": "n/a",
            "bitmap_mode": "BYTE",
            "checksum_algo": "CRC32_0001",
            "checksum_size": 4,
            "blocks/checksum": 1,
            "reseed_checksum": "False",
        }
        #        pp = pprint.PrettyPrinter(indent=4)
        #        pp.pprint(partclone_info_dict)
        self.assertDictEqual(expected_partclone_info_dict, partclone_info_dict)

    def test_partclone_parsing_dd_img(self):
        partclone_info_output_dd_image = """Partclone v0.3.13 http://partclone.org
Showing info of image (-)
This is not partclone image.
Partclone fail, please check /var/log/partclone.log !"""
        partclone_info_dict = Partclone.parse_partclone_info_output(partclone_info_output_dd_image)
        self.assertDictEqual({}, partclone_info_dict)
