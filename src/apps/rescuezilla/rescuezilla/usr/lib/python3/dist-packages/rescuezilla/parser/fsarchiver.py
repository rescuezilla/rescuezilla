# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
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

import collections
import re


class Fsarchiver:
    @staticmethod
    def parse_fsarchiver_output(fsarchiver_output):
        """Converts the STDOUT of `fsarchiver probe detailed` into a dictionary. See unit tests for a complete example"""
        drives = collections.OrderedDict([])
        partitions = collections.OrderedDict([])
        # Split input string into a two element list using the *second* heading
        initial_split = re.split(".*DEVICE.*FILESYS.*LABEL.*SIZE.*MAJ.*MIN.*LONGNAME.*UUID.*", fsarchiver_output)
        # The second half is the second element
        second_half = initial_split[1]
        # Remove the first heading by splitting on it, then taking the second element.
        first_half = re.split(".*DISK.*NAME.*SIZE.*MAJ.*MIN.*", initial_split[0])[1]

        print("first half is " + str(first_half))
        drives_list = first_half.splitlines()
        for drive_line in drives_list:
            drive_line = drive_line.strip()
            if drive_line != '' and drive_line != '\n':
                # Remove first and last square bracket
                drive_line = drive_line[1:-1]
                d = re.split('] \[', drive_line)
                try:
                    shortdevname = d[0].strip()
                    drives[shortdevname] = {'model_name': d[1].strip(), 'capacity': d[2].strip(), 'maj': d[3].strip(),
                                            'min': d[4].strip()}
                except IndexError:
                    print("Unable to parse: " + str(drive_line) + ". Skipping")
        print("drives:" + str(drives))

        partition_list = second_half.splitlines()
        for partition_line in partition_list:
            partition_line = partition_line.strip()
            if partition_line != '' and partition_line != '\n':
                # Remove first and last square bracket
                partition_line = partition_line[1:-1]
                d = re.split('] \[', partition_line)
                try:
                    shortdevname = d[0].strip()
                    partitions[shortdevname] = {'filesystem': d[1].strip(),
                                                'label': d[2].strip(), 'size': d[3].strip(), 'maj': d[4].strip(),
                                                'min': d[5].strip(), 'longdevname': d[6].strip(),
                                                'uuid': d[7].strip()}
                except IndexError:
                    print("Unable to parse: " + str(partition_line) + ". Skipping")
        print("partitions: " + str(partitions))
        return drives, partitions