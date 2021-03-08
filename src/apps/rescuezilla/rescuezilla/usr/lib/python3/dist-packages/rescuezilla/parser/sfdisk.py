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

import utility

"""
    Note: collections.OrderedDict() is used to ensure dictionary remembers the insertion order (which since Python
    3.8 is the behaviour of even the default dictionary implementation). This is important as traditional MBR (DOS)
    partition tables with extended partitioning may have device node ordering such as "sda1 -> sda5 -> sda3".
    However, currently `fsarchiver probe` produces output that is pre-sorted making this moot until fsarchiver is
    replaced.

"""

empty_sfdisk_bug_url = "https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in-louvetchs-ubuntu-1604-releases"
EMPTY_SFDISK_MSG = utility._(
    "The backup's extended partition information is empty. If the backup contains extended partitions, these will not restore correctly. All data is still fully recoverable but manual intervention is required to fully restore any extended partitions. Please consult {url} for information and assistance. The destination drive has not yet been modified. Do you wish to continue with the restore?").format(
    url=empty_sfdisk_bug_url)


class Sfdisk:
    @staticmethod
    def parse_sfdisk_dump_output(sfdisk_output):
        sfdisk_dict = {'partitions': collections.OrderedDict()}
        for line in sfdisk_output.splitlines():
            #print("Processing sfdisk line: " + str(line))
            try:
                split = re.split(":", line)
                key = split[0].strip()
                if key == "":
                    # One empty line is to be expected
                    continue
                value = split[1].strip()
                if key == "label":
                    sfdisk_dict['label'] = value
                elif key == "label-id":
                    sfdisk_dict['label_id'] = value
                elif key == "device":
                    sfdisk_dict['device'] = value
                elif key == "unit":
                    sfdisk_dict['unit'] = value
                elif key == "first-lba":
                    sfdisk_dict['first_lba'] = int(value)
                elif key == "last-lba":
                    sfdisk_dict['last_lba'] = int(value)
                elif key.startswith("/dev/"):
                    sfdisk_dict['partitions'][key] = {}
                    part_split = re.split(",", value)
                    if key == "label":
                        print("Part split is " + str(part_split))
                    for component in part_split:
                        try:
                            component.strip()
                            component_split = re.split("=", component)
                            component_key = component_split[0].strip()
                            component_value = component_split[1].strip()
                            if component_key == "start":
                                sfdisk_dict['partitions'][key]['start'] = int(component_value)
                            elif component_key == "size":
                                sfdisk_dict['partitions'][key]['size'] = int(component_value)
                            elif component_key == "type":
                                sfdisk_dict['partitions'][key]['type'] = component_value
                            elif component_key == "uuid":
                                sfdisk_dict['partitions'][key]['uuid'] = component_value
                        except IndexError:
                            print("Unable to parse: " + str(value) + " in " + str(line) + ". Skipping")
                else:
                    print("Unknown key" + key)
            except IndexError:
                print("Unable to parse: " + str(split) + " in " + str(line) + ". Skipping")

        return sfdisk_dict

    @staticmethod
    def parse_sfdisk_show_geometry(line):
        temp_dict = {}
        m = utility.REMatcher(line)
        if m.match(r"^/dev/.*:\s*([0-9]*)\scylinders,\s([0-9]*)\sheads,\s([0-9]*)\ssectors/track$"):
            temp_dict['cylinders'] = int(m.group(1))
            temp_dict['heads'] = int(m.group(2))
            temp_dict['sectors'] = int(m.group(3))
            return temp_dict
        else:
            print("Could not process: " + line)
            return temp_dict

    # The Foxclone image format doesn't keep track of the disk capacity, and neither does the sfdisk file.
    # However it has each partition's start offset and size, so finding the largest provides an estimate
    # of drive capacity.
    # Adapted from CombinedDriveState's get_first_partition
    # TODO: Make more pythonic and more efficient
    @staticmethod
    def get_drive_capacity_estimate(partition_list):
        temp_tuple_list = []
        block_size = 512
        for key in partition_list.keys():
            temp_tuple_list.append((key, partition_list[key]['start']*block_size + partition_list[key]['size']*block_size))
        temp_tuple_list.sort(key=lambda x: x[1], reverse=True)
        print("highest " + str(temp_tuple_list))
        return temp_tuple_list[0]