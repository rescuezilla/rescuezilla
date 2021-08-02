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
from datetime import datetime
from pathlib import Path

from babel.dates import format_datetime

import utility
from utility import Utility

# Apart GTK is a simple Partclone frontend [1]. It operates on partitions, but does not backup partition tables etc.
#
# The handling of ApartGtk images is not derived from the ApartGtk source code, but has been implemented purely based
# on examining the images generated from using that program. Any errors in parsing here are Rescuezilla's own.
#
# [1] https://github.com/alexheretic/apart-gtk
class ApartGtkImage:
    def __init__(self, absolute_apart_gtk_img_path):
        self.image_format = "APART_GTK_FORMAT"
        self.absolute_path = absolute_apart_gtk_img_path
        self.enduser_filename = os.path.join(os.path.basename(os.path.dirname(self.absolute_path)), "*.apt.*")
        self.user_notes = ""
        self.warning_dict = {}

        # Clonezilla format
        self.ebr_dict = {}
        self.efi_nvram_dat_absolute_path = None
        self.short_device_node_partition_list = []
        self.short_device_node_disk_list = [self.enduser_filename]
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
        self.image_format_dict_dict = collections.OrderedDict([])

        dir = Path(absolute_apart_gtk_img_path).parent.as_posix()
        print("ApartGtk directory : " + dir)

        # Gather all the Apart GTK partclone images in the current folder
        self._apart_gtk_metadata_dict_dict = {}
        image_absolute_path_list = glob.glob(os.path.join(dir, "*.apt.*"))
        max_timestamp = datetime.min
        estimated_num_byte = 0
        for image_absolute_path in image_absolute_path_list:
            image_filename = os.path.basename(image_absolute_path)
            # Parse the filename into a dictionary
            metadata_dict = ApartGtkImage._parse_filename(image_filename)
            estimated_num_byte += os.path.getsize(image_absolute_path)
            # TODO: Convert the timestamp string into a form Python can use
            node_with_timestamp = metadata_dict['name'] + "-" + metadata_dict['timestamp']
            if metadata_dict['inprogress']:
               self.warning_dict[image_absolute_path] = "Partition image appears to be partially complete (or still in progress)"
               continue
            else:
                # Place the filenames into the description field for a tidy vertical list of partitions in the
                # combined image
                self.user_notes += os.path.basename(image_absolute_path) + "\n"
                with Utility.setlocale('C'):
                    # Convert ApartGtk's English human-readable string to Python datetime
                    metadata_dict['timestamp'] = datetime.strptime(metadata_dict['timestamp'], "%Y-%m-%dT%H%M")
                    if max_timestamp < metadata_dict['timestamp']:
                        max_timestamp = metadata_dict['timestamp']
                self._apart_gtk_metadata_dict_dict[image_absolute_path] = metadata_dict

            if metadata_dict['filesystem'] != "dd":
                self.image_format_dict_dict[node_with_timestamp] = {'type': "partclone",
                                                     'absolute_filename_glob_list': [image_absolute_path],
                                                     'compression': ApartGtkImage._convert_compression_identifier(metadata_dict['compression']),
                                                     'filesystem': metadata_dict['filesystem'],
                                                     # Assumption that binary is valid.
                                                     'binary': "partclone." + metadata_dict['filesystem'],
                                                     'is_lvm_logical_volume': False}
            else:
                self.image_format_dict_dict[node_with_timestamp] = {'type': "dd",
                                                     'absolute_filename_glob_list': [image_absolute_path],
                                                     'compression': ApartGtkImage._convert_compression_identifier(metadata_dict['compression']),
                                                     'binary': "partclone.dd",
                                                     'is_lvm_logical_volume': False}

            self.short_device_node_disk_list += node_with_timestamp

        # Convert to a string that's consistent with the rest of Rescuezilla
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(max_timestamp.timestamp()))
        print("Last modified timestamp (max timestamp): " + self.last_modified_timestamp)

        self.size_bytes = estimated_num_byte
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))
        self.is_needs_decryption = False

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for key in self.image_format_dict_dict:
            flat_string += "(" + key + ": " + self.flatten_partition_string(key) + ") "
            index += 1
        return flat_string

    def flatten_partition_string(self, key):
        return self.image_format_dict_dict[key]['filesystem'] + " " + \
               Utility.human_readable_filesize(self._compute_partition_size_byte_estimate(key))

    def does_image_key_belong_to_device(self, image_format_dict_key):
        return True

    def has_partition_table(self):
        # No ApartGtk images has a partition table backup. (Ignoring the case where eg, encrypted drive could be
        # imaged as raw dd backup)
        return False

    def get_absolute_mbr_path(self):
        return None

    # Parses the Apart GTK filename into a dictionary structure *without* further processing
    @staticmethod
    def _parse_filename(apart_gtk_filename):
        m = utility.REMatcher(apart_gtk_filename)
        # Filename in format "(name)-(timestamp).apt.(filesystem).(compression)", with an optional ".inprogress" suffix
        if not m.match(r"^([a-zA-Z0-9-_+]*)-([0-9]+-[0-9]+-[0-9]+T[0-9]+)\.apt\.([a-zA-Z0-9+]+)\.([a-zA-Z0-9]+)([\.inprogress]?)"):
            raise ValueError("Unable to process ApartGTK image: " + apart_gtk_filename)
        else:
            apart_gtk_image_dict = {
            'name': m.group(1),
            'timestamp': m.group(2),
            'filesystem': m.group(3),
            'compression': m.group(4),
            'inprogress': False
        }
        if "inprogress" in apart_gtk_filename:
            apart_gtk_image_dict['inprogress'] = True
        return apart_gtk_image_dict

    def _compute_partition_size_byte_estimate(self, key):
        num_bytes = 0
        # Should only be 1 element in the list, but apart-gtk may one day support splitting images
        for absolute_filename in self.image_format_dict_dict[key]['absolute_filename_glob_list']:
            num_bytes = os.path.getsize(absolute_filename)
        return num_bytes

    # Convert the string used to identify compression in Apart GTK's filename into the same format used elsewhere in
    # Rescuezilla
    @staticmethod
    def _convert_compression_identifier(filename_string):
        if filename_string == "gz":
            return "gzip"
        # After grepping Apart GTK's source code for any missing compression formats, its "src/util.py" references
        # "also support .zstd from v0.14", so Rescuezilla matches this by checking for both "zst" and "zstd".
        elif filename_string == "zst" or filename_string == "zstd":
            return "zstd"
        elif filename_string == "uncompressed":
            return "uncompressed"
        else:
            raise Exception("Unable to query Apart GTK's file compression: " + filename_string)
