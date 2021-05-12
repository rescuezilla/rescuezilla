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
import re

import utility

"""
    Note: collections.OrderedDict() is used to ensure dictionary remembers the insertion order (which since Python
    3.8 is the behaviour of even the default dictionary implementation). This is important as traditional MBR (DOS)
    partition tables with extended partitioning may have device node ordering such as "sda1 -> sda5 -> sda3".
    However, currently `fsarchiver probe` produces output that is pre-sorted making this moot until fsarchiver is
    replaced.

"""


class Parted:
    # The following is required to fully parse the Clonezilla image format which does not use parted's --machine flag
    # for easy processing.
    #
    # TODO: Consider switching Rescuezilla's *internal* processing to use the parted --machine output
    @staticmethod
    def parse_parted_output(parted_output):
        """Converts the STDOUT of `fsarchiver probe detailed` into a dictionary. See unit tests for a complete example"""
        parted_dict = collections.OrderedDict([])
        parted_dict['partitions'] = collections.OrderedDict([])

        initial_split = re.split(r"Number\s*Start\s*End\s*Size.*Flags", parted_output)
        #print("looking at " + str(initial_split) )
        metadata_list = initial_split[0].splitlines()
        for metadata_line in metadata_list:
            #print("looking at line " + metadata_line)
            m = utility.REMatcher(metadata_line)
            if metadata_line.strip() == "":
                # Skip this line
                continue
            # Processing: Model: ATA VBOX HARDDISK (scsi)
            elif m.match(r"Model: (.+)"):
                parted_dict['model'] = m.group(1)
            # Processing: Disk /dev/sdc: 2147483648B
            elif m.match(r"Disk ([a-zA-Z0-9_/]+): ([0-9]+)([a-zA-Z]+)"):
                parted_dict['long_dev_node'] = m.group(1)
                parted_dict['capacity'] = int(m.group(2))
                parted_dict['units'] = m.group(3)
            # Processing: Sector size (logical/physical): 512B/512B
            elif m.match(r"Sector size .logical/physical.: ([0-9]+)[a-zA-Z]+/([0-9]+)[a-zA-Z]+"):
                parted_dict['logical_sector_size'] = int(m.group(1))
                parted_dict['physical_sector_size'] = int(m.group(2))
            # Processing: Partition Table: gpt
            elif m.match(r"Partition Table: ([a-zA-Z]+)"):
                parted_dict['partition_table'] = m.group(1)
            # Processing: Disk Flags:
            elif m.match(r"Disk Flags:(.*)"):
                parted_dict['flags'] = m.group(1)
            else:
                print("Could not process: " + metadata_line)

        if len(initial_split) > 1:
            partition_list = initial_split[1].splitlines()
            for partition_line in partition_list:
                if partition_line.strip() == "":
                    continue
                if parted_dict['partition_table'] == "gpt":
                    # Number  Start       End          Size         File system     Name  Flags
                    #  1      1048576B    65011711B    63963136B    ext4
                    column_title = re.search("Number\s+Start\s+End\s+Size\s+File system\s+Name\s+Flags", parted_output).group(0)
                    partition_line = partition_line.ljust(len(column_title), " ")
                    # Pad the line with spaces to allow splicing.
                    partition_number = int(partition_line[0:column_title.index("Start") - 1].strip())
                    parted_dict['partitions'][partition_number] = collections.OrderedDict()
                    #print("Looking at line " + partition_line)
                    parted_dict['partitions'][partition_number]['start'] = int(
                        partition_line[column_title.index("Start"):column_title.index("End") - 1].strip()[:-1])
                    parted_dict['partitions'][partition_number]['end'] = int(
                        partition_line[column_title.index("End"):column_title.index("Size") - 1].strip()[:-1])
                    parted_dict['partitions'][partition_number]['size'] = int(
                        partition_line[column_title.index("Size"):column_title.index("File system") - 1].strip()[:-1])
                    parted_dict['partitions'][partition_number]['filesystem'] = partition_line[column_title.index(
                        "File system"):column_title.index("Name") - 1].strip()
                    parted_dict['partitions'][partition_number]['name'] = partition_line[
                                                                     column_title.index("Name"):column_title.index(
                                                                         "Flags") - 1].strip()
                    parted_dict['partitions'][partition_number]['flags'] = partition_line[column_title.index("Flags"):len(
                        partition_line)].strip()

                # Number  Start       End          Size         Type      File system     Flags
                #  1      1048576B    91226111B    90177536B    primary   ext4
                elif parted_dict['partition_table'] == "msdos":
                    column_title = re.search("Number\s+Start\s+End\s+Size\s+Type\s+File system\s+Flags", parted_output).group(0)
                    partition_line = partition_line.ljust(len(column_title), " ")
                    # Pad the line with spaces to allow splicing.
                    partition_number = int(partition_line[0:column_title.index("Start") - 1].strip())
                    parted_dict['partitions'][partition_number] = collections.OrderedDict()
                    #print("Looking at line " + partition_line)
                    parted_dict['partitions'][partition_number]['start'] = int( partition_line[column_title.index("Start"):column_title.index("End") - 1].strip()[:-1])
                    parted_dict['partitions'][partition_number]['end'] = int( partition_line[column_title.index("End"):column_title.index("Size") - 1].strip()[:-1])
                    parted_dict['partitions'][partition_number]['size'] = int( partition_line[column_title.index("Size"):column_title.index("Type") - 1].strip()[:-1])
                    parted_dict['partitions'][partition_number]['type'] = partition_line[column_title.index("Type"):column_title.index("File system") - 1].strip()
                    parted_dict['partitions'][partition_number]['filesystem'] = partition_line[column_title.index( "File system"):column_title.index("Flags") - 1].strip()
                    parted_dict['partitions'][partition_number]['flags'] = partition_line[column_title.index("Flags"):len( partition_line)].strip()
                else:
                    print("Could not process: " + partition_line)
        return parted_dict

    # Get all indexes to Parted dictionary for partitions with flag
    #
    # This function is loosely adapted from Clonezilla's "is_gpt_disk_with_bios_boot_part_in_legacy_bios"
    # function from its "sbin/ocs-function", and also the "check_ntfs_boot_partition" function
    #
    # IMPORTANT: The returned value is in Parted's partition's indexing (a partition *number*, not a string or
    # long_device_node)
    @staticmethod
    def get_partitions_containing_flag(parted_dict, flag):
        found_partition_keys_list = []
        for partition_key in parted_dict['partitions'].keys():
            if Parted.has_flag(parted_dict, partition_key, flag):
                found_partition_keys_list += [partition_key]
        return found_partition_keys_list

    @staticmethod
    def has_flag(parted_dict, partition_key, flag):
        if partition_key in parted_dict['partitions'].keys() and 'flags' in parted_dict['partitions'][partition_key].keys()\
                and flag in parted_dict['partitions'][partition_key]['flags']:
            return True
        else:
            return False
