# ----------------------------------------------------------------------
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

from parser.foxclone_image import FoxcloneImage


class FoxcloneTest(unittest.TestCase):
    def test_foxclone_parsing(self):
        input_foxclone_string = """07 Mar 2021, 09:49
Compression:YES
Split files:NO
Model:ATA VBOX HARDDISK
Serial:VB42efc350-3a91f739
Mount point:sdi
Partition:sdi1 : ntfs : primary : 52MB : 53% used [System Reserved] : Flags-boot *Windows 10*
Blocks:sdi1,26972
Partition:sdi2 : <unknown> : primary : 30.8GB : 100% used
Blocks:sdi2,30800000
Partition:sdi4 : extended
Blocks:sdi4,0
Partition:sdi5 : ext4 : logical : 21.8GB : 22% used *Ubuntu 18.04.5 LTS*
Blocks:sdi5,4778704
Partition:sdi3 : ntfs : primary : 522MB : 83% used : Flags-diag
Blocks:sdi3,421176
End
"""
        foxclone_dict = FoxcloneImage.parse_dot_backup(input_foxclone_string)
        expected_foxclone_dict = {
            'timestamp': "07 Mar 2021, 09:49",
            'is_compressed': True,
            'is_split': False,
            'model': 'ATA VBOX HARDDISK',
            'serial': 'VB42efc350-3a91f739',
            'original_mount_point': 'sdi',
            'partitions': {
                'sdi1': {
                    'fs': 'ntfs',
                    'type': 'primary',
                    'num_blocks': 26972,
                },
                'sdi2': {
                    'fs': '<unknown>',
                    'type': 'primary',
                    'num_blocks': 30800000,
                },
                'sdi4': {
                    'type': 'extended',
                    'num_blocks': 0,
                },
                'sdi5': {
                    'fs': 'ext4',
                    'type': 'logical',
                    'num_blocks': 4778704,
                },
                'sdi3': {
                    'fs': 'ntfs',
                    'type': 'primary',
                    'num_blocks': 421176,
                },

            }
        }
        #print("actual:" + str(foxclone_dict))
        self.assertDictEqual(expected_foxclone_dict, foxclone_dict)

    def test_foxclone_swap_parsing(self):
        # Manually configured string based on a real example.
        synthentic_input = """07 Mar 2021, 09:49
Compression:YES
Split files:NO
Model:ATA VBOX HARDDISK
Serial:VB42efc350-3a91f739
Mount point:sdi
Partition:sdi1 : swap : deadbeef-0000-1234-5678-deadbeef0000
Blocks:sdi1,26972
End
"""
        # TODO: Test Foxclone swap partitions as logical partitions
        foxclone_dict = FoxcloneImage.parse_dot_backup(synthentic_input)
        expected_foxclone_dict = {
            'timestamp': "07 Mar 2021, 09:49",
            'is_compressed': True,
            'is_split': False,
            'model': 'ATA VBOX HARDDISK',
            'serial': 'VB42efc350-3a91f739',
            'original_mount_point': 'sdi',
            'partitions': {
                'sdi1': {
                    'fs': 'swap',
                    'type': 'deadbeef-0000-1234-5678-deadbeef0000',
                    'num_blocks': 26972,
                },
            }
        }
        print("actual:" + str(foxclone_dict))
        self.assertDictEqual(expected_foxclone_dict, foxclone_dict)


