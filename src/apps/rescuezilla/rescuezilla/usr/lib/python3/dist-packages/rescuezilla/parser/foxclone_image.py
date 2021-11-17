# ----------------------------------------------------------------------
#   Copyright (C) 2021 Rescuezilla.com <rescuezilla@gmail.com>
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
import glob
import os
import re
from datetime import datetime
from pathlib import Path

from babel.dates import format_datetime

# The handling of Foxclone images is not derived from the Foxclone source code, but has been implemented purely based
# on examining the images generated from using that program. Any errors in parsing here are Rescuezilla's own.
from parser.sfdisk import Sfdisk
from utility import Utility, _


class FoxcloneImage:
    def __init__(self, absolute_foxclone_img_path, enduser_filename, filename):
        self.image_format = "FOXCLONE_FORMAT"
        self.absolute_path = absolute_foxclone_img_path
        self.enduser_filename = enduser_filename
        self.user_notes = ""
        self.warning_dict = {}

        # Clonezilla format
        self.ebr_dict = {}
        self.efi_nvram_dat_absolute_path = None
        self.short_device_node_partition_list = []
        self.short_device_node_disk_list = []
        self.lvm_vg_dev_dict = {}
        self.lvm_logical_volume_dict = {}
        self.sfdisk_chs_dict = None
        self.dev_fs_dict = {}
        self.size_bytes = 0
        self.enduser_readable_size = ""
        self.is_needs_decryption = False
        self.normalized_sfdisk_dict = {'absolute_path': None, 'sfdisk_dict': {'partitions': {}}, 'file_length': 0}
        self.parted_dict = {'partitions': {}}
        self.post_mbr_gap_dict = {}

        if filename.endswith(".backup"):
            prefix = filename.split(".backup")[0]
            print("prefix: " + prefix)
        else:
            raise ValueError("Expected Foxclone backup to end with .backup: " + absolute_foxclone_img_path)

        dirname = os.path.dirname(absolute_foxclone_img_path)
        self.foxclone_dict = FoxcloneImage.parse_dot_backup(Utility.read_file_into_string(absolute_foxclone_img_path))
        with Utility.setlocale('C'):
            # Convert Foxclone's English human-readable string to Python datetime
            foxclone_datetime = datetime.strptime(self.foxclone_dict['timestamp'], "%d %b %Y, %H:%M")
        # Convert to a string that's consistent with the rest of Rescuezilla
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(foxclone_datetime.timestamp()))
        print("Last modified timestamp " + self.last_modified_timestamp)

        dir = Path(absolute_foxclone_img_path).parent.as_posix()
        print("Foxclone directory : " + dir)

        sfdisk_absolute_path = os.path.join(dirname, prefix + ".sfdisk")
        self.normalized_sfdisk_dict = Sfdisk.generate_normalized_sfdisk_dict(sfdisk_absolute_path, self)

        if 'device' in self.normalized_sfdisk_dict['sfdisk_dict'].keys():
            self.short_device_node_disk_list = [self.normalized_sfdisk_dict['sfdisk_dict']['device']]

        self._mbr_absolute_path = None
        mbr_path_string = os.path.join(dirname, prefix + ".grub")
        if os.path.exists(mbr_path_string):
            self._mbr_absolute_path = mbr_path_string
        else:
            self.warning_dict[self.short_device_node_disk_list] = "Missing MBR"

        self.image_format_dict_dict = collections.OrderedDict([])
        for short_device_node in self.foxclone_dict['partitions'].keys():
            type = self.foxclone_dict['partitions'][short_device_node]['type']
            if type == "extended":
                # Foxclone never has a partition associated with the extended partition.
                continue
            filesystem = self.foxclone_dict['partitions'][short_device_node]['fs']
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            # The partclone image Foxclone creates can be compressed, and can be split into multiple files, depending
            # on the settings the user configures. The compression and split settings are saved in the metadata file,
            # which was already parsed above. The filename patterns may be as follows:
            #
            # Uncompressed, no split: 20210307.sdj1.img
            # Uncompressed, split: 20210307.sdj1.img.00
            # Compressed, no split: 20210307.sdj1.img
            # Compressed, split: 20210307.sdj1.img.00
            image_match_string = prefix + "." + short_device_node + ".img"
            if self.foxclone_dict['is_compressed']:
                # Foxclone only supports gzip compression
                image_match_string += ".gz"
            if self.foxclone_dict['is_split']:
                # The split filenames goes 88, 89, 9000, 9001 etc. It looks like partclone does this, perhaps to
                # prevent any issue around lexical ordering. This is good, because lexical ordering is used here.
                image_match_string += ".*"
            image_match_path_string = os.path.join(dirname, image_match_string)
            print(image_match_path_string)
            # Get absolute path partition images. Eg, [/path/to/20200813_part3.000, /path/to/20200813_part3.001 etc]
            abs_partclone_image_list = glob.glob(image_match_path_string)
            # Sort by alphabetical sort. Lexical sort not required here because fixed number of digits (so no risk of
            # "1, 10, 2, 3" issues), and partclone manages this when the number of digits is no longer fixed (see
            # above)
            abs_partclone_image_list.sort()
            if len(abs_partclone_image_list) == 0 and filesystem != "swap":
                self.warning_dict[short_device_node] = _(
                    "Cannot find partition's associated partclone image") + "\n        " + image_match_string
                continue

            if filesystem == "swap":
                self.image_format_dict_dict[short_device_node] = {'type': "swap",
                                                                  # TODO: Make the fact the UUID gets placed in 'type' field less confusing.
                                                                  'uuid':  self.foxclone_dict['partitions'][short_device_node]['type'],
                                                                  'label': "",
                                                                  "prefix": prefix,
                                                                  'is_lvm_logical_volume': False}
            elif filesystem != "<unknown>":
                # Detect compression because while Foxclone only supports gzip as of writing, but this presumably may change in future.
                self.image_format_dict_dict[short_device_node] = {'type': "partclone",
                                                                  'absolute_filename_glob_list': abs_partclone_image_list,
                                                                  'compression': Utility.detect_compression(abs_partclone_image_list),
                                                                  'filesystem': filesystem,
                                                                  # Assumption that binary is valid.
                                                                  'binary': "partclone." + filesystem,
                                                                  "prefix": prefix,
                                                                  'is_lvm_logical_volume': False}
            else:
                # Detect compression because while Foxclone only supports gzip as of writing, but this presumably may change in future.
                self.image_format_dict_dict[short_device_node] = {'type': "dd",
                                                                  'absolute_filename_glob_list': abs_partclone_image_list,
                                                                  'compression': Utility.detect_compression(abs_partclone_image_list),
                                                                  'binary': "partclone.dd",
                                                                  "prefix": prefix,
                                                                  'is_lvm_logical_volume': False}

        notes_abs_path = os.path.join(dirname, prefix + ".note.txt")
        if os.path.exists(notes_abs_path):
            self.user_notes = Utility.read_file_into_string(notes_abs_path)

        # Foxclone doesn't keep track of the drive capacity, so estimate it from sfdisk partition table backup
        last_partition_key, last_partition_final_byte = Sfdisk.get_highest_offset_partition(self.normalized_sfdisk_dict)
        self.size_bytes = last_partition_final_byte
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))

        for image_format_dict_key in self.image_format_dict_dict.keys():
            estimated_size_bytes = self._compute_partition_size_byte_estimate(image_format_dict_key)
            self.image_format_dict_dict[image_format_dict_key]['estimated_size_bytes'] = estimated_size_bytes

        self.is_needs_decryption = False

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for short_device_node in self.foxclone_dict['partitions'].keys():
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(short_device_node) + ") "
            index += 1
        return flat_string

    def flatten_partition_string(self, short_device_node):
        flat_string = ""
        base_device_node, partition_number = Utility.split_device_string(short_device_node)
        type = self.foxclone_dict['partitions'][short_device_node]['type']
        if type == "extended":
            flat_string = type
            return flat_string
        else:
            fs = self.foxclone_dict['partitions'][short_device_node]['fs']
            if fs is None:
                flat_string += "unknown"
            elif fs != "":
                flat_string += self.foxclone_dict['partitions'][short_device_node]['fs'] + " "

            num_bytes = self._compute_partition_size_byte_estimate(short_device_node)
            flat_string += " " + str(Utility.human_readable_filesize(num_bytes))
            return flat_string

    def _compute_partition_size_byte_estimate(self, short_device_node):
        # It's unclear what the Foxclone .backup file's blocksize is referring to, so use the sfdisk partition
        # size in blocks (which assumes 512 byte block size)
        num_bytes = 512 * self.normalized_sfdisk_dict['sfdisk_dict']['partitions']['/dev/' + short_device_node][
            'size']
        return num_bytes

    def does_image_key_belong_to_device(self, image_format_dict_key):
        return True

    def has_partition_table(self):
        # All Foxclone images have partition tables.
        return True

    def get_absolute_mbr_path(self):
        return self._mbr_absolute_path

    @staticmethod
    def string_to_boolean(value):
        if value == "YES":
            return True
        elif value == "NO":
            return False
        else:
            raise Exception("Unknown value: " + value)

    @staticmethod
    def parse_dot_backup(dot_backup_contents):
        dot_backup_dict = {'partitions': collections.OrderedDict()}

        initial_split = dot_backup_contents.split('\n', 1)
        dot_backup_dict['timestamp'] = initial_split[0]
        if len(initial_split) < 2:
            raise Exception("Could not split: " + dot_backup_contents)

        for line in initial_split[1].splitlines():
            print("Processing foxclone backup line: " + str(line))
            if line == "End":
                return dot_backup_dict
            try:
                split = re.split(":", line)
                key = split[0].strip()
                value = split[1].strip()
                if key == "Compression":
                    dot_backup_dict['is_compressed'] = FoxcloneImage.string_to_boolean(value)
                elif key == "Split files":
                    dot_backup_dict['is_split'] = FoxcloneImage.string_to_boolean(value)
                elif key == "Model":
                    dot_backup_dict['model'] = value
                elif key == "Serial":
                    dot_backup_dict['serial'] = value
                elif key == "Mount point":
                    dot_backup_dict['original_mount_point'] = value
                elif key.startswith("Partition"):
                    short_device_node = split[1].strip()
                    second_field = split[2].strip()
                    # The second field is usually the filesystem, followed by the type (primary/logical). Except when
                    # the type is extended, in which case there's no filesystem field.
                    if second_field == "extended":
                        dot_backup_dict['partitions'][short_device_node] = {'type': second_field}
                    else:
                        third_field = split[3].strip()
                        # TODO: Figure out how Foxclone handles swap partitions as logical partitions, if at all.
                        dot_backup_dict['partitions'][short_device_node] = {'fs': second_field, 'type': third_field}
                    # The rest of this line is the human-readable used-space, human-readable percentage used,
                    # description and boot flags the boot flags are already saved in the sfdisk partition backup so
                    # aren't needed here. Also, if the type is "extended" there isn't any thing further.
                elif key == "Blocks":
                    block_split = re.split(",", value)
                    short_device_node = block_split[0].strip()
                    num_blocks = int(block_split[1].strip())
                    dot_backup_dict['partitions'][short_device_node]['num_blocks'] = num_blocks
                else:
                    print("Unknown key" + key)
            except IndexError:
                print("Unable to parse: " + line + ". Skipping")
        raise Exception("Failed to reach 'End' line in:\n\n" + dot_backup_contents)
