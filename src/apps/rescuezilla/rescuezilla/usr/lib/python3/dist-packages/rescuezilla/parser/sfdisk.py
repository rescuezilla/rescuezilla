# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
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

import collections
import os
import re
import shutil
from os.path import isfile

import utility

"""
    Note: collections.OrderedDict() is used to ensure dictionary remembers the insertion order (which since Python
    3.8 is the behaviour of even the default dictionary implementation). This is important as traditional MBR (DOS)
    partition tables with extended partitioning may have device node ordering such as "sda1 -> sda5 -> sda3".
    However, currently `fsarchiver probe` produces output that is pre-sorted making this moot until fsarchiver is
    replaced.

"""

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

    # Adapted from CombinedDriveState's get_first_partition
    # TODO: Make more pythonic and more efficient
    # TODO: Move function to a more suitable class.
    @staticmethod
    def get_highest_offset_partition(normalized_sfdisk_dict):
        temp_tuple_list = []
        block_size = 512
        sfdisk_partition_dict = normalized_sfdisk_dict['sfdisk_dict']['partitions']
        print(str(sfdisk_partition_dict))
        for key in sfdisk_partition_dict.keys():
            # The Foxclone image format doesn't keep track of the disk capacity, and neither does the sfdisk file.
            # However it has each partition's start offset and size, so finding the largest provides an estimate
            # of drive capacity.
            temp_tuple_list.append((key, sfdisk_partition_dict[key]['start'] * block_size + sfdisk_partition_dict[key]['size'] * block_size))
        temp_tuple_list.sort(key=lambda x: x[1], reverse=True)
        print("sorted offset list: " + str(temp_tuple_list))
        if len(temp_tuple_list) == 0:
            # Some image formats may not have any partitions (eg, Clonezilla saveparts when filesystem directly on disk)
            # FIXME: Handle images without sfdisk partition tables better
            return "NO_PARTITIONS", 0
        else:
            return temp_tuple_list[0]

    @staticmethod
    def has_dos_partition_table(normalized_sfdisk_dict):
        if 'label' not in normalized_sfdisk_dict['sfdisk_dict']:
            # Older versions of sfdisk did not support GPT but also didn't have the label field. So all these disks
            # can be assumed to have a DOS partition table.
            return True
        elif 'dos' == normalized_sfdisk_dict['sfdisk_dict']['label']:
            return True
        else:
            return False

    @staticmethod
    def generate_normalized_sfdisk_dict(sfdisk_absolute_path, image):
        sfdisk_filename = os.path.basename(sfdisk_absolute_path)
        normalized_sfdisk_dict = {'absolute_path': None, 'sfdisk_dict': {'partitions': {}}, 'file_length': 0}
        if isfile(sfdisk_absolute_path):
            sfdisk_string = utility.Utility.read_file_into_string(sfdisk_absolute_path)
            normalized_sfdisk_dict['absolute_path'] = sfdisk_absolute_path
            normalized_sfdisk_dict['file_length'] = len(sfdisk_string)
            if normalized_sfdisk_dict['file_length'] == 0:
                image.warning_dict[sfdisk_filename] = Sfdisk.get_empty_sfdisk_msg()
            else:
                normalized_sfdisk_dict['sfdisk_dict'] = Sfdisk.parse_sfdisk_dump_output(sfdisk_string)
        elif image.has_partition_table():
            # Only display warning message for image if it has an MBR backup, as Clonezilla can do a saveparts
            # on drives without partition table and it's expected to be missing a MBR and an sfdisk file.
            image.warning_dict[sfdisk_filename] = Sfdisk.get_empty_sfdisk_msg()
        return normalized_sfdisk_dict

    @staticmethod
    def get_sfdisk_cmd_list(destination_device_node, prefer_old_sfdisk_binary=False):
        sfdisk_cmd_list = []
        warning_message = ""
        if prefer_old_sfdisk_binary:
            # To maximize backwards compatibility, use old version of sfdisk to restore partition table (if available)
            # This is important as the sfdisk output format changed between 2012 and 2016.
            old_sfdisk_binary = "sfdisk" + "." + "v2.20.1." + utility.Utility.get_memory_bus_width()
            if shutil.which(old_sfdisk_binary) is not None:
                sfdisk_cmd_list = [old_sfdisk_binary, "-fx", destination_device_node]
            else:
                warning_message = "Could not find old sfdisk binary to maximize backwards compatibility: " + str(
                    old_sfdisk_binary) + ". Will fallback to modern sfdisk version.\n"

        if not prefer_old_sfdisk_binary or len(sfdisk_cmd_list) == 0:
            sfdisk_binary = "sfdisk"
            if shutil.which(sfdisk_binary) is None:
                warning_message += "Could not find binary: " + str(sfdisk_cmd_list) + "\n\n"
                return None, warning_message
            else:
                sfdisk_cmd_list = [sfdisk_binary, "-f", destination_device_node]
        return sfdisk_cmd_list, warning_message

    @staticmethod
    def get_empty_sfdisk_msg():
        empty_sfdisk_bug_url = "https://github.com/rescuezilla/rescuezilla/wiki/Missing-sfdisk-warning-message"
        empty_sfdisk_msg = utility._(
            "The backup's extended partition information is empty. If the backup contains an extended partition this will not restore correctly. All data is still fully recoverable but manual intervention is required to fully restore data within the extended partition. Please consult {url} for information and assistance.").format(
            url=empty_sfdisk_bug_url)
        return empty_sfdisk_msg