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

import collections
import copy

from utility import Utility, _


# Implementation of Clonezilla's "/sbin/ocs-get-part-info" bash script.
#
# Clonezilla combines drive information from the output of `lsblk`, `blkid`, `parted` and `sfdisk`, because
# each is lacking in different ways (especially around providing filesystems that partclone can understand).
#
#
#
# This approach does not seem particularly efficient, but to maximize Clonezilla image compatibility (both for backup
# and restore), the data flow has been re-implemented.
class CombinedDriveState:
    @staticmethod
    def construct_combined_drive_state_dict(lsblk_json_dict, blkid_dict, osprober_dict, parted_dict_dict,
                                            sfdisk_dict_dict):
        drive_state = collections.OrderedDict([])

        # Copy the block device list because it will be modified during the loop iteration.
        block_device_list = copy.deepcopy(lsblk_json_dict['blockdevices'])
        # Loop over lsblk's nested structure and create a structure that reflects Clonezilla's information access
        # patterns.
        # FIXME: The following codeblock appends to the list, so there is a potential risk of an infinite loop when
        # FIXME: querying certain drive/partition configurations that should be investigated.
        i = 0
        while i < len(block_device_list):
            current_block_device = block_device_list[i]
            drive_longdevname = current_block_device['name']
            drive_state[drive_longdevname] = collections.OrderedDict([])
            drive_state[drive_longdevname]['partition_table'] = None
            drive_state[drive_longdevname]['has_raid_member_filesystem'] = False

            # Drive model
            drive_state[drive_longdevname]['model'] = current_block_device['model']
            drive_state[drive_longdevname]['serial'] = current_block_device['serial']
            # Drive capacity (in bytes)
            drive_state[drive_longdevname]['capacity'] = current_block_device['size']
            if drive_state[drive_longdevname]['capacity'] == "":
                drive_state[drive_longdevname]['capacity'] = parted_dict_dict[drive_longdevname]['capacity']

            drive_state[drive_longdevname]['type'] = current_block_device['type']
            if drive_state[drive_longdevname]['type'] == "":
                print("lsblk type field is blank.")
                # TODO Get type from parted as per Clonezilla
                # drive_state[drive_longdevname]['capacity'] = parted_dict_dict['type']

            if drive_longdevname in parted_dict_dict.keys():
                if 'model' in  parted_dict_dict[drive_longdevname].keys():
                    drive_state[drive_longdevname]['model'] = parted_dict_dict[drive_longdevname]['model']
                if 'partition_table' in  parted_dict_dict[drive_longdevname].keys():
                    drive_state[drive_longdevname]['partition_table'] = parted_dict_dict[drive_longdevname]['partition_table']
                if 'flags' in  parted_dict_dict[drive_longdevname].keys():
                    drive_state[drive_longdevname]['flags'] = parted_dict_dict[drive_longdevname]['flags']
                if 'logical_sector_size' in  parted_dict_dict[drive_longdevname].keys():
                    drive_state[drive_longdevname]['logical_sector_size'] = parted_dict_dict[drive_longdevname]['logical_sector_size']
                if 'physical_sector_size' in  parted_dict_dict[drive_longdevname].keys():
                    drive_state[drive_longdevname]['physical_sector_size'] = parted_dict_dict[drive_longdevname]['physical_sector_size']

            # drive_state[drive_longdevname]['fstype'] = current_block_device['fstype']

            # Filesystem (or LVM) written directly to disk, without partition table.
            # If the device has no detected partitions and has no partition table, add itself as a child so that all
            # subsequent logic handles the device as a partition. The base device key (eg /dev/sda) still is suitable
            # for lookup of data from data arrays.
            #
            # The filesystem directly on disk case has a parted dict entry, so use non-null fstype
            if 'children' not in current_block_device.keys() and (drive_state[drive_longdevname][
                'partition_table'] is None or current_block_device['fstype'] is not None):
                rewritten_block_device = copy.deepcopy(current_block_device)
                # Overwrite the existing type (probably 'disk') so it's treated as a partition.
                rewritten_block_device['type'] = 'part'
                # Wrap the dictionary as a list, because that's how the lsblk output normally is.
                current_block_device['children'] = [rewritten_block_device]

            if 'children' in current_block_device.keys():
                drive_state[drive_longdevname]['partitions'] = collections.OrderedDict([])
                for lsblk_partition_dict in current_block_device['children']:
                    partition_longdevname = lsblk_partition_dict['name']
                    drive_state[drive_longdevname]['partitions'][partition_longdevname] = {}
                    partition_state = drive_state[drive_longdevname]['partitions'][partition_longdevname]

                    if lsblk_partition_dict['fstype'] == 'linux_raid_member':
                        drive_state[drive_longdevname]['has_raid_member_filesystem'] = True

                    # Partition size (in bytes)
                    partition_state['size'] = lsblk_partition_dict['size']
                    current_parted_dict = {}
                    try:
                        # Split may fail for some device nodes
                        base_device_node, partition_number = Utility.split_device_string(partition_longdevname)
                        if drive_longdevname in parted_dict_dict.keys():
                            current_parted_dict = parted_dict_dict[drive_longdevname]
                    except Exception as e:
                        current_parted_dict = {}

                    if 'partitions' in current_parted_dict.keys() and partition_number in current_parted_dict[
                        'partitions'].keys():
                        if partition_state['size'] == "":
                            partition_state['size'] = current_parted_dict['partitions'][partition_number]['size']

                    partition_state['filesystem'] = ""
                    if partition_longdevname in blkid_dict.keys():
                        if 'TYPE' in blkid_dict[partition_longdevname].keys():
                            partition_state['filesystem'] = blkid_dict[partition_longdevname]['TYPE']
                        if 'UUID' in blkid_dict[partition_longdevname].keys():
                            partition_state['uuid'] = blkid_dict[partition_longdevname]['UUID']
                        if 'LABEL' in blkid_dict[partition_longdevname].keys():
                            partition_state['label'] = blkid_dict[partition_longdevname]['LABEL']
                        if 'PARTLABEL' in blkid_dict[partition_longdevname].keys():
                            partlabel = blkid_dict[partition_longdevname]['PARTLABEL']
                            if partlabel == "Microsoft reserved partition":
                                partition_state['filesystem'] = "MS_Reserved_Partition"

                    # if partition_state['filesystem'] == "" and drive_longdevname in sfdisk_dict_dict.keys() and partition_longdevname in sfdisk_dict_dict[drive_longdevname].keys():
                    #    sfdisk_dict = sfdisk_dict_dict[drive_longdevname][partition_longdevname]

                    if 'partitions' in current_parted_dict.keys() and partition_number in current_parted_dict[
                        'partitions'].keys():
                        if partition_state['filesystem'] == "" and 'filesystem' in current_parted_dict['partitions'][
                            partition_number].keys():
                            partition_state['filesystem'] = current_parted_dict['partitions'][partition_number][
                                'filesystem']
                        if current_parted_dict['partitions'][partition_number].keys():
                            drive_state[drive_longdevname]['partitions'][partition_longdevname]['flags'] = \
                            current_parted_dict['partitions'][partition_number]['flags']
                    if partition_longdevname in osprober_dict.keys():
                        partition_state['os_bootloader'] = osprober_dict[partition_longdevname]

                    # FIXME: I don't think parted partition number guaranteed to increment based on device node partition number.
                    # Get type field different from Clonezilla. Clonezilla uses lsblk first, because it's faster than parted, but this is not an issue here because all
                    # data is cached.

                    if 'partitions' in current_parted_dict.keys() and partition_number in current_parted_dict[
                        'partitions'].keys():
                        if 'type' in current_parted_dict['partitions'][partition_number].keys():
                            partition_state['type'] = current_parted_dict['partitions'][partition_number]['type']
                        if 'type' not in partition_state.keys() or partition_state['type'] == "":
                            partition_state['type'] = lsblk_partition_dict['type']
                        partition_state['start'] = current_parted_dict['partitions'][partition_number]['start']
                        partition_state['end'] = current_parted_dict['partitions'][partition_number]['end']
                        partition_state['flags'] = current_parted_dict['partitions'][partition_number]['flags']

                    # Extract out subchildren for non-partition devices (like RAID and LVMs) so they can be processed
                    # as top level devices in the next iteration of the loop. This ensures RAID (/dev/md127) and LVM
                    # (/dev/mapper/vg-lv) have their information available in the state dictionary
                    if 'children' in lsblk_partition_dict.keys():
                        for device in lsblk_partition_dict['children']:
                            if device['type'] != 'part':
                                print("Appending " + str(device))
                                block_device_list.append(device)
                    # ...The final case to test is if the partition itself is not actually a partition:
                    elif lsblk_partition_dict['type'] != 'part':
                        print("Appending " + str(lsblk_partition_dict))
                        block_device_list.append(lsblk_partition_dict)
            i += 1

        return drive_state

    @staticmethod
    def flatten_partition_list(selected_drive):
        """Turns partitions belonging to a selected drive into a nice string"""
        flat_string = ""
        if 'fstype' in selected_drive.keys():
            drive_fstype = selected_drive['fstype']
            if drive_fstype is not None:
                flat_string += drive_fstype + " "
        if 'partitions' in selected_drive.keys():
            keys_list = list(selected_drive['partitions'].keys())
            for i in range(len(keys_list)):
                partition = selected_drive['partitions'][keys_list[i]]
                print(str(selected_drive))
                flat_string += "("
                if "label" in partition.keys():
                    label = str(partition['label'])
                    flat_string += label + ", "
                size_in_bytes = partition['size']
                enduser_readable_size = Utility.human_readable_filesize(int(size_in_bytes))
                flat_string += enduser_readable_size + ", "
                fs = partition['filesystem']
                if fs != "":
                    flat_string += fs
                if "type" in partition.keys():
                    type = partition['type']
                    if type == "extended":
                        flat_string += type
                if "os_bootloader" in partition.keys():
                    if "os_description" in partition['os_bootloader'].keys():
                        os_description = str(partition['os_bootloader']['os_description'])
                        if os_description != "":
                            flat_string += ", " + os_description + " "
                    if "os_label" in partition['os_bootloader'].keys():
                        os_label = str(partition['os_bootloader']['os_label'])
                        if os_label != "":
                            flat_string += "[" + os_label + ", "
                    if "os_type" in partition['os_bootloader'].keys():
                        os_type = str(partition['os_bootloader']['os_type'])
                        if os_type != "":
                            flat_string += os_type + "]"
                if i == (len(keys_list) - 1):
                    # If final element, end with a bracket
                    flat_string += ")"
                else:
                    flat_string += "), "
        return flat_string

    @staticmethod
    def flatten_partition_description(drive_dict, drive_key, partition_key):
        """Turns partitions belonging to a selected drive into a nice string"""
        enduser_drive_number = 1 + list(drive_dict.keys()).index(drive_key)
        if 'partitions' in drive_dict[drive_key].keys():
            enduser_partition_number = 1 + list(drive_dict[drive_key]['partitions'].keys()).index(partition_key)
            part_dict = drive_dict[drive_key]['partitions'][partition_key]
            partition_string = CombinedDriveState.flatten_part(part_dict)
        else:
            # Case where no partition table in destination device
            # TODO: Handle this better
            enduser_partition_number = 0
            partition_string = CombinedDriveState.flatten_part(drive_dict[drive_key])
        flat_string = _("Drive {drive_number}").format(drive_number=str(enduser_drive_number)) + ", " + _("Partition {partition_number}").format(partition_number=str(enduser_partition_number)) + ": " + partition_string
        return flat_string

    @staticmethod
    def flatten_part(part_dict):
        flat_string = ""
        if 'size' in part_dict.keys():
            size_in_bytes = part_dict['size']
            enduser_readable_size = Utility.human_readable_filesize(int(size_in_bytes))
            flat_string += enduser_readable_size + " "
        if 'filesystem' in part_dict.keys():
            flat_string += part_dict['filesystem'] + " "
        if 'label' in part_dict.keys():
            label = part_dict['label']
            flat_string += label
        if 'type' in part_dict.keys():
            type = part_dict['type']
            if type == "extended":
                flat_string += type
        return flat_string

    @staticmethod
    def flatten_drive(drive_dict):
        flat_string = ""
        if 'capacity' in drive_dict.keys():
            size_in_bytes = drive_dict['capacity']
            enduser_readable_size = Utility.human_readable_filesize(int(size_in_bytes))
            flat_string += enduser_readable_size
        return flat_string

    # Important in calculating the hidden data after MBR in most accurate way possible.
    @staticmethod
    def get_first_partition(partition_list):
        # TODO: Make more pythonic and more efficient
        temp_tuple_list = []
        for key in partition_list.keys():
            if 'start' in partition_list[key].keys():
                temp_tuple_list.append((key, partition_list[key]['start']))
        temp_tuple_list.sort(key=lambda x: x[1])
        print("lowest " + str(temp_tuple_list))
        if len(temp_tuple_list) == 0:
            # FIXME: Handle better
            return "NO_PARTITIONS", 0
        else:
            return temp_tuple_list[0]
