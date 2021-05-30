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
import base64
import collections
import glob
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from babel.dates import format_datetime

from parser.sfdisk import Sfdisk
from utility import Utility, _


# The handling of Redo Rescue images is not derived from the Redo Rescue source code, but has been implemented purely
# based on examining the images generated from using that program. Any errors in parsing here are Rescuezilla's own.
class RedoRescueImage:
    def __init__(self, absolute_redorescue_json_path, enduser_filename, filename):
        self.image_format = "REDORESCUE_FORMAT"
        self.absolute_path = absolute_redorescue_json_path
        self.enduser_filename = enduser_filename
        self.is_needs_decryption = False
        # Redo Rescue's MBR backup is within its JSON backup file.
        self.mbr_absolute_path = None
        # Redo Rescue's sfdisk backup is within its JSON backup file.
        self.sfdisk_absolute_path = None
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
        self.parted_dict = {'partitions': {}}
        self.post_mbr_gap_dict = {}

        if filename.endswith(".redo"):
            prefix = filename.split(".redo")[0]
            print("prefix: " + prefix)
        else:
            raise ValueError("Expected RedoRescue backup to end with .backup: " + absolute_redorescue_json_path)

        dirname = os.path.dirname(absolute_redorescue_json_path)
        self.redo_dict = json.loads(Utility.read_file_into_string(absolute_redorescue_json_path))
        print(json.dumps(self.redo_dict, indent=4, sort_keys=True))

        with Utility.setlocale('C'):
            # Convert Redo Rescue's English human-readable string to Python datetime
            redo_datetime = datetime.strptime(self.redo_dict['timestamp'], "%a, %d %b %Y %H:%M:%S %z")
        # Convert to a string that's consistent with the rest of Rescuezilla
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(redo_datetime.timestamp()))
        print("Last modified timestamp " + self.last_modified_timestamp)

        # TODO: Remove the need for this
        self.short_device_node_disk_list = ["unknown"]

        dir = Path(absolute_redorescue_json_path).parent.as_posix()
        print("Redo Rescue directory : " + dir)

        self.normalized_sfdisk_dict = {'absolute_path': None, 'sfdisk_dict': {'partitions': {}}, 'file_length': 0}
        if len(self.redo_dict['sfd_bin']) != 0:
            sfdisk_bytes = base64.b64decode(self.redo_dict['sfd_bin'])
            print("Decoded: " + str(sfdisk_bytes))
            # Immediately write the decoded bytes to a temp file. This allows the same logic to be shared between other
            # images.
            f = tempfile.NamedTemporaryFile(mode='wb', delete=False)
            f.write(sfdisk_bytes)
            f.close()
            self.normalized_sfdisk_dict = Sfdisk.generate_normalized_sfdisk_dict(f.name, self)
        else:
            self.warning_dict[enduser_filename] = Sfdisk.get_empty_sfdisk_msg()

        self.size_bytes = self.redo_dict['drive_bytes']
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))

        self.image_format_dict_dict = collections.OrderedDict([])
        for short_device_node in self.redo_dict['parts'].keys():
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            image_match_string = os.path.join(dirname, self.redo_dict['id'] + "_" + short_device_node + "_" + "*.img")
            print(image_match_string)
            # Get absolute path partition images. Eg, [/path/to/20200813_part3.000, /path/to/20200813_part3.001 etc]
            abs_partclone_image_list = glob.glob(image_match_string)
            # Sort by alphabetical sort. Lexical sort not required here because fixed number of digits (so no risk
            # of "1, 10, 2, 3" issues)
            abs_partclone_image_list.sort()
            if len(abs_partclone_image_list) == 0:
                self.warning_dict[short_device_node] = _(
                    "Cannot find partition's associated partclone image") + "\n        " + image_match_string
                continue
            filesystem = self.redo_dict['parts'][short_device_node]['fs']
            if filesystem is None:
                filesystem = "<unknown>"
            # Redo Rescue only supports gzip as of writing, but this presumably may change in future.
            detected_compression = Utility.detect_compression(abs_partclone_image_list)
            suggested_partclone_binary = "partclone." + filesystem
            if shutil.which(suggested_partclone_binary) is not None:
                self.image_format_dict_dict[short_device_node] = {'type': "partclone",
                                 'absolute_filename_glob_list': abs_partclone_image_list,
                                 'compression': detected_compression,
                                 'filesystem': filesystem,
                                 'binary': suggested_partclone_binary,
                                 "prefix": prefix,
                                 'is_lvm_logical_volume': False}
            else:
                self.image_format_dict_dict[short_device_node] = {'type': "dd",
                                     'absolute_filename_glob_list': abs_partclone_image_list,
                                     'compression': detected_compression,
                                     'binary': "partclone.dd",
                                     "prefix": prefix,
                                     'is_lvm_logical_volume': False}

        if 'notes' in self.redo_dict.keys():
            self.user_notes = self.redo_dict['notes']

    def does_image_key_belong_to_device(self, image_format_dict_key):
        return True

    def has_partition_table(self):
        # All Redo Rescue images have an associated MBR file
        return True

    def get_absolute_mbr_path(self):
        # TODO: Clean this up (by switching to a named tmp directory)
        f = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        mbr_bytes = base64.b64decode(self.redo_dict['mbr_bin'])
        # Write bytes to file
        f.write(mbr_bytes)
        return f.name

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for short_device_node in self.redo_dict['parts'].keys():
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(short_device_node) + ") "
            index += 1
        return flat_string

    def flatten_partition_string(self, short_device_node):
        flat_string = ""
        base_device_node, partition_number = Utility.split_device_string(short_device_node)
        # Otherwise, the value detected by partclone.info must be used (which is known to be unreliable).
        fs = self.redo_dict['parts'][short_device_node]['fs']
        if fs is None:
            flat_string += "unknown"
        elif fs != "":
            flat_string += self.redo_dict['parts'][short_device_node]['fs'] + " "
        num_bytes = self._compute_partition_size_byte_estimate(short_device_node)
        flat_string += " " + str(Utility.human_readable_filesize(num_bytes))
        return flat_string

    def _compute_partition_size_byte_estimate(self, short_device_node):
        return self.redo_dict['parts'][short_device_node]['bytes']

    # Redo Rescue's metadata is a JSON file ending in .redo. Unfortunately this conflicts with the format of Redo
    # Backup and Recovery 0.9.2, which also uses a metadata file ending in .redo (this was changed to .backup for
    # v0.9.3-v1.0.4).
    #
    # The best way to delineate this situation is to try reading the JSON file, if it succeeds then it's a Redo Rescue
    # image.
    @staticmethod
    def is_valid_json(absolute_path):
        try:
            json.loads(Utility.read_file_into_string(absolute_path))
            return True
        except ValueError:
            return False
