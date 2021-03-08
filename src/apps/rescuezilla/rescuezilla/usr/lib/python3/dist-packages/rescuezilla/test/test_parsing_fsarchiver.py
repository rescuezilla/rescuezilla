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

from parser.fsarchiver import Fsarchiver
from parser.fsarchiver_image import FsArchiverImage


class FsArchiverTest(unittest.TestCase):
    def test_fsarchiver_archinfo_parsing(self):
        # Output of: fsarchiver archinfo file.fsa
        input_fsarchiver_archinfo_string = """====================== archive information ======================
Archive type: 			filesystems
Filesystems count: 		5
Archive id: 			6041cf71
Archive file format: 		FsArCh_002
Archive created with: 		0.8.5
Archive creation date: 		2021-03-13_05-23-37
Archive label: 			<none>
Minimum fsarchiver version:	0.6.4.0
Compression level: 		8 (zstd level 8)
Encryption algorithm: 		none

===================== filesystem information ====================
Filesystem id in archive: 	0
Filesystem format: 		ext4
Filesystem label: 		
Filesystem uuid: 		dbba5b33-43d6-49f8-bd2d-5c14c326f7ac
Original device: 		/dev/sdb1
Original filesystem size: 	620.80 MB (650952704 bytes)
Space used in filesystem: 	664.00 KB (679936 bytes)

===================== filesystem information ====================
Filesystem id in archive: 	1
Filesystem format: 		ext4
Filesystem label: 		
Filesystem uuid: 		f1fea003-1cf7-4a9e-9d9c-0d7cc23d1e3d
Original device: 		/dev/sdc1
Original filesystem size: 	989.93 MB (1038016512 bytes)
Space used in filesystem: 	1.25 MB (1314816 bytes)

===================== filesystem information ====================
Filesystem id in archive: 	2
Filesystem format: 		btrfs
Filesystem label: 		
Filesystem uuid: 		9264f052-6695-445c-aa40-87f1dc6045bf
Original device: 		/dev/sdg1
Original filesystem size: 	256.00 MB (268435456 bytes)
Space used in filesystem: 	3.50 MB (3670016 bytes)

===================== filesystem information ====================
Filesystem id in archive: 	3
Filesystem format: 		vfat
Filesystem label: 		NO NAME    
Filesystem uuid: 		<none>
Original device: 		/dev/sdg2
Original filesystem size: 	458.09 MB (480337920 bytes)
Space used in filesystem: 	4.00 KB (4096 bytes)

===================== filesystem information ====================
Filesystem id in archive: 	4
Filesystem format: 		ntfs
Filesystem label: 		<unknown>
Filesystem uuid: 		27C70B8D355A8E6D
Original device: 		/dev/sdg3
Original filesystem size: 	2.80 GB (3006263296 bytes)
Space used in filesystem: 	14.86 MB (15581184 bytes)

"""
        fsarchiver_archinfo_dict = FsArchiverImage.parse_fsarchiver_archinfo_output(input_fsarchiver_archinfo_string)
        expected_fsarchiver_archinfo_dict = {
            'archive_type': 'filesystems',
            'fs_count': 5,
            'archive_id': '6041cf71',
            'archive_file_format': 'FsArCh_002',
            'created_with': '0.8.5',
            'date': '2021-03-13_05-23-37',
            'archive_label': '<none>',
            'minimum_fsarchiver_version': '0.6.4.0',
            'compression_level': '8 (zstd level 8)',
            'encryption_algorithm': 'none',
            'filesystems': {
                '0': {
                    'filesystem_format': 'ext4',
                    'filesystem_label': '',
                    'filesystem_uuid': 'dbba5b33-43d6-49f8-bd2d-5c14c326f7ac',
                    'original_long_device_node': '/dev/sdb1',
                    'size_bytes': 650952704,
                    'used_bytes': 679936,
                },
                '1': {
                    'filesystem_format': 'ext4',
                    'filesystem_label': '',
                    'filesystem_uuid': 'f1fea003-1cf7-4a9e-9d9c-0d7cc23d1e3d',
                    'original_long_device_node': '/dev/sdc1',
                    'size_bytes': 1038016512,
                    'used_bytes': 1314816,
                },
                '2': {
                    'filesystem_format': 'btrfs',
                    'filesystem_label': '',
                    'filesystem_uuid': '9264f052-6695-445c-aa40-87f1dc6045bf',
                    'original_long_device_node': '/dev/sdg1',
                    'size_bytes': 268435456,
                    'used_bytes': 3670016,
                },
                '3': {
                    'filesystem_format': 'vfat',
                    'filesystem_label': 'NO NAME',
                    'filesystem_uuid': '<none>',
                    'original_long_device_node': '/dev/sdg2',
                    'size_bytes': 480337920,
                    'used_bytes': 4096,
                },
                '4': {
                    'filesystem_format': 'ntfs',
                    'filesystem_label': '<unknown>',
                    'filesystem_uuid': '27C70B8D355A8E6D',
                    'original_long_device_node': '/dev/sdg3',
                    'size_bytes': 3006263296,
                    'used_bytes': 15581184,
                }
            }
        }
        self.assertDictEqual(expected_fsarchiver_archinfo_dict, fsarchiver_archinfo_dict)


def test_fsarchiver_probe_parsing():
    fsarchiver_probe_detailed_contents = """[======DISK======] [=============NAME==============] [====SIZE====] [MAJ] [MIN]
[fd0             ] [                               ] [     1.41 MB] [  2] [  0]
[sda             ] [VBOX HARDDISK                  ] [    32.00 GB] [  8] [  0]
[sdb             ] [HARDDISK                       ] [     7.74 GB] [  8] [ 16]
[sdc             ] [VBOX HARDDISK                  ] [    50.00 GB] [  8] [ 32]
[sdd             ] [VBOX HARDDISK                  ] [     2.00 TB] [  8] [ 48]
[sde             ] [TOSHIBA USB DRV                ] [     7.46 GB] [  8] [ 64]
[sr0             ] [CD-ROM                         ] [   756.28 MB] [ 11] [  0]
[sr1             ] [CD-ROM                         ] [    57.65 MB] [ 11] [  1]
[nvme0n1         ] [ORCL-VBOX-NVME-VER12                    ] [     2.00 TB] [259] [  0]

[=====DEVICE=====] [==FILESYS==] [======LABEL======] [====SIZE====] [MAJ] [MIN] [==============LONGNAME==============] [=================UUID=================] 
[loop0           ] [squashfs   ] [<unknown>        ] [   654.89 MB] [  7] [  0] [/dev/loop0                          ] [<unknown>                             ] 
[sda1            ] [ntfs       ] [<unknown>        ] [    32.00 GB] [  8] [  1] [/dev/sda1                           ] [0000000000000000                      ] 
[sdb1            ] [ext4       ] [ASDF             ] [   903.00 MB] [  8] [ 17] [/dev/sdb1                           ] [11111111-1111-1111-1111-111111111111  ] 
[sdb2            ] [ntfs       ] [FDSA             ] [   660.00 MB] [  8] [ 18] [/dev/sdb2                           ] [2222222222222222                      ] 
[sdb3            ] [vfat       ] [LABELRANDOM      ] [     6.21 GB] [  8] [ 19] [/dev/sdb3                           ] [3333-3333                             ] 
[sdc1            ] [ntfs       ] [Recovery         ] [   529.00 MB] [  8] [ 33] [/dev/sdc1                           ] [4444444444444444                      ] 
[sdc2            ] [vfat       ] [<unknown>        ] [    99.00 MB] [  8] [ 34] [/dev/sdc2                           ] [5555-5555                             ] 
[sdc3            ] [<unknown>  ] [<unknown>        ] [    16.00 MB] [  8] [ 35] [/dev/sdc3                           ] [<unknown>                             ] 
[sdc4            ] [ntfs       ] [<unknown>        ] [    49.37 GB] [  8] [ 36] [/dev/sdc4                           ] [6666666666666666                      ] 
[sdd1            ] [ext4       ] [<unknown>        ] [     2.00 TB] [  8] [ 49] [/dev/sdd1                           ] [77777777-7777-7777-7777-777777777777  ] 
[sdd5            ] [swap       ] [<unknown>        ] [     2.00 GB] [  8] [ 53] [/dev/sdd5                           ] [88888888-8888-8888-8888-888888888888  ] 
[nvme0n1p1       ] [ext4       ] [<unknown>        ] [    32.00 GB] [259] [  1] [/dev/nvme0n1p1                      ] [99999999-9999-9999-9999-999999999999  ] """
    Fsarchiver.parse_fsarchiver_output(fsarchiver_probe_detailed_contents)
    # assert_true("message", False)
    # assert_false("message", True)

    os_prober_contents = """/dev/sdc2@/efi/Microsoft/Boot/bootmgfw.efi:Windows Boot Manager:Windows:efi
/dev/sdd1:Debian GNU/Linux 10 (buster):Debian:linux"""
    #drive_state_dict = Fsarchiver.construct_drive_state_dict(fsarchiver_probe_detailed_contents,
    #                                                                            os_prober_contents)
    #print("drive state dcitonary\n\n\n\n " + str(drive_state_dict))
    #print("\n\n\n\n")


# Run tests
test_fsarchiver_probe_parsing()
