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
from parser.fsarchiver import Fsarchiver


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
