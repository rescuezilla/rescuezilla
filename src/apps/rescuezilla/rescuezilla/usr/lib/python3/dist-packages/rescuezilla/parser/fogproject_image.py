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
from os.path import isfile
from pathlib import Path

from babel.dates import format_datetime

# The handling of FOG Project images is not derived from the FOG Project source code, but has been implemented purely
# based on examining the images generated from using that program. Any errors in parsing here are Rescuezilla's own.
from parser.partclone import Partclone
from parser.sfdisk import Sfdisk
from utility import Utility, _


# A single FOG Project image folder can contain multiple disks (d1.partitions, d2.partitions etc). For the purposes of
# Rescuezilla, each disk image is treated as a different object. Unlike Clonezilla, there's no shared state between
# these multidisk images, so treating them separately makes sense.
#
# FOG Project supports a variety of image formats. No attempt has been made to support the RAW dd format as the
# files appear to be just eg, d.000, d.001 with no metadata which is difficult to delineate from other images.
class FogProjectImage:
    def __init__(self, absolute_fogproject_img_path, enduser_filename, filename):
        self.image_format = "FOGPROJECT_FORMAT"
        self.absolute_path = absolute_fogproject_img_path
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

        if filename.endswith(".partitions") and not filename.endswith(".minimum.partitions"):
            prefix = filename.split(".partitions")[0]
            print("prefix: " + prefix)
        else:
            raise ValueError("Expected FOG Project backup to end with .partition: " + absolute_fogproject_img_path)

        statbuf = os.stat(self.absolute_path)
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(statbuf.st_mtime))
        print("Last modified timestamp " + self.last_modified_timestamp)

        dir = Path(absolute_fogproject_img_path).parent.as_posix()
        print("FOG Project directory : " + dir)

        dirname = os.path.dirname(absolute_fogproject_img_path)
        # FogProject has its main sfdisk file named eg, 'd1.partitions', but it may also have an unmodified sfdisk
        # file named eg, "d1.minimum.partitions). This approach is apparently used to support restoring to disks
        # smaller than the original. Rescuezilla intends to implement something similar [1], but for now we always
        # use the original, unmodified file (which may be "d1.partitions" if the FOG Project's resize checkbox was not
        # ticked during backup).
        #
        # [1] https://github.com/rescuezilla/rescuezilla/issues/18
        minimum_partitions_sfdisk_path = os.path.join(dir, prefix + ".minimum.partitions")
        if os.path.exists(minimum_partitions_sfdisk_path):
            # TODO: Implement FOG Project's intelligent partition resizing. [1] Rescuezilla has growing filesystems,
            # TODO: but not yet modifying partitions.
            # [1] https://github.com/rescuezilla/rescuezilla/issues/18
            print("Found minimum partitions, but ignoring until partition resize implemented")

        sfdisk_absolute_path = absolute_fogproject_img_path
        self.normalized_sfdisk_dict = Sfdisk.generate_normalized_sfdisk_dict(sfdisk_absolute_path, self)

        # FOG Project images sometimes contains a file named eg, "d1.original.fstypes" which contains the association
        # between partition numbers with filesystems considered resizable, and their associated device nodes.
        self.original_fstypes_dict = {}
        original_fstypes_filepath = os.path.join(dir, prefix + ".original.fstypes")
        if isfile(original_fstypes_filepath):
            self.original_fstypes_dict = FogProjectImage.parse_original_fstypes_output(
                Utility.read_file_into_string(original_fstypes_filepath))

        # FOG Project images sometimes contains a file named eg, "d1.fixed_sized_partitions" which is a colon separated
        # list of the partition numbers that *cannot* be resized.
        self.fixed_size_partitions = []
        fixed_sized_partitions_path = os.path.join(dir, prefix + ".fixed_sized_partitions")
        if os.path.exists(fixed_sized_partitions_path):
            fixed_sized_partitions_string = Utility.read_file_into_string(fixed_sized_partitions_path).strip()
            self.fixed_size_partitions = fixed_sized_partitions_string.split(":")
            # Convert every element to from a string to an int
            self.fixed_size_partitions = list(map(int, self.fixed_size_partitions))

        # FOG Project images sometimes contains a file named eg, "d1.original.swapuuids" which contains the association
        # between a partition number and the UUID of the Linux swap partition that resides on there.
        self.original_swapuuids_dict = {}
        original_swapuuids_filepath = os.path.join(dir, prefix + ".original.swapuuids")
        if isfile(original_swapuuids_filepath):
            self.original_swapuuids_dict = FogProjectImage.parse_original_swapuuids_output(
                Utility.read_file_into_string(original_swapuuids_filepath))

        if 'device' in self.normalized_sfdisk_dict['sfdisk_dict'].keys():
            self.long_device_node_disk_list = [self.normalized_sfdisk_dict['sfdisk_dict']['device']]

        # FOG Project images sometimes has a file named eg, ".size" that contains the drive size in bytes.
        size_path = os.path.join(dir, prefix + ".size")
        if os.path.exists(size_path):
            # When the file exists, use it.
            size_string = Utility.read_file_into_string(size_path).strip()
            # TODO: split smarter
            split = size_string.split(":")
            self.size_bytes = int(split[1])

        self._mbr_absolute_path = None
        mbr_path_string = os.path.join(dirname, prefix + ".mbr")
        if os.path.exists(mbr_path_string):
            self._mbr_absolute_path = mbr_path_string
        else:
            self.warning_dict[self.normalized_sfdisk_dict['sfdisk_dict']['device']] = "Missing MBR"

        self.has_grub = False
        has_grub_path_string = os.path.join(dirname, prefix + "has_grub")
        if os.path.exists(has_grub_path_string):
            self.has_grub = True

        if 'device' in self.normalized_sfdisk_dict['sfdisk_dict'].keys():
            self.short_device_node_disk_list = [self.normalized_sfdisk_dict['sfdisk_dict']['device']]

        self.partclone_info_dict_dict = collections.OrderedDict([])
        self.image_format_dict_dict = collections.OrderedDict([])
        for long_device_node in self.normalized_sfdisk_dict['sfdisk_dict']['partitions'].keys():
            if self.normalized_sfdisk_dict['sfdisk_dict']['partitions'][long_device_node]['type'] == "27":
                # TODO populate
                continue
            base_device_node, partition_number = Utility.split_device_string(long_device_node)
            if partition_number in self.original_swapuuids_dict.keys():
                # Swap handled below
                continue
            # The partclone image FOG Project creates can be compressed as either gzip or zstd, can be split
            # into multiple files, depending on the settings the user configures. The compression format is not encoded
            # in the filename.
            #
            # Split:    d1p3.img     (may or may not be compressed)
            # No split: d1p3.img.001 (may or may not be compressed)
            image_match_string = prefix + "p" + str(partition_number) + ".img*"
            image_match_path_string = os.path.join(dirname, image_match_string)
            print(image_match_path_string)
            # Get absolute path partition images. Eg, [/path/to/dlp3.img.001, /path/to/dlp3.img.002 etc]
            abs_image_list = glob.glob(image_match_path_string)
            # Sort by alphabetical sort. Lexical sort not required here because fixed number of digits (so no risk of
            # "1, 10, 2, 3" issues), and partclone manages this when the number of digits is no longer fixed (see
            # above)
            abs_image_list.sort()
            if len(abs_image_list) == 0:
                self.warning_dict[long_device_node] = _(
                    "Cannot find partition's associated partclone image") + "\n        " + image_match_string
                continue

            detected_compression = Utility.detect_compression(abs_image_list)
            # May be PartImage image.
            self.partclone_info_dict_dict[long_device_node] = Partclone.get_partclone_info_dict(abs_image_list, long_device_node, detected_compression)
            filesystem = self.partclone_info_dict_dict[long_device_node]['filesystem'].lower()
            print(str(self.partclone_info_dict_dict))

            if filesystem != "<unknown>" and filesystem != "raw":
                self.image_format_dict_dict[long_device_node] = {'type': "partclone",
                                 'absolute_filename_glob_list': abs_image_list,
                                 'compression': detected_compression,
                                 'filesystem': filesystem,
                                 'binary': "partclone." + filesystem,
                                 "prefix": prefix,
                                 'is_lvm_logical_volume': False}
            else:
                self.image_format_dict_dict[long_device_node] = {'type': "dd",
                                     'absolute_filename_glob_list': abs_image_list,
                                     'compression': detected_compression,
                                     'filesystem': filesystem,
                                     'binary': "partclone.dd",
                                     "prefix": prefix,
                                     'is_lvm_logical_volume': False}

        for swapuuid_key in self.original_swapuuids_dict.keys():
            # The key to the Swap UUID is the partition number, but long_device_node is much more convenient
            long_device_node = Utility.join_device_string(self.short_device_node_disk_list[0], swapuuid_key)
            print("Converting swap partition number " + str(swapuuid_key) + " to key " + long_device_node)
            self.image_format_dict_dict[long_device_node] = {'type': "swap",
                                                             'uuid': self.original_swapuuids_dict[swapuuid_key],
                                                             'label': "",
                                                             'filesystem': "swap",
                                                             "prefix": prefix,
                                                             'is_lvm_logical_volume': False}
        if self.size_bytes == 0:
            # When the file doesn't exist, estimate drive capacity from sfdisk partition table backup
            last_partition_key, last_partition_final_byte = Sfdisk.get_highest_offset_partition(self.normalized_sfdisk_dict)
            self.size_bytes = last_partition_final_byte
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))
        self.is_needs_decryption = False

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for long_device_node in self.image_format_dict_dict.keys():
            base_device_node, partition_number = Utility.split_device_string(long_device_node)
            flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(long_device_node) + ") "
            index += 1
        return flat_string

    def does_image_key_belong_to_device(self, image_format_dict_key):
        return True

    def has_partition_table(self):
        # All FOG Project images have partition tables.
        return True

    def get_absolute_mbr_path(self):
        return self._mbr_absolute_path

    def flatten_partition_string(self, long_device_node):
        flat_string = ""
        fs = self._get_human_readable_filesystem(long_device_node)
        if fs != "":
            flat_string = fs + " "
        partition_size_bytes = self._compute_partition_size_byte_estimate(long_device_node)
        flat_string += Utility.human_readable_filesize(partition_size_bytes)
        return flat_string

    def _get_human_readable_filesystem(self, long_device_node):
        if long_device_node in self.image_format_dict_dict.keys():
            return self.image_format_dict_dict[long_device_node]['filesystem']
        else:
            if long_device_node in self.original_fstypes_dict.keys():
                return self.original_fstypes_dict[long_device_node]['filesystem']
            else:
                return ""

    # Estimates size of each filesystem image, ideally based on the partition table, but otherwise by querying the total
    # number of bytes used by the image files. Does NOT use partclone.info, which too slow to run on every image.
    def _compute_partition_size_byte_estimate(self, long_device_node):
        # It's unclear what the FOG Project .backup file's blocksize is referring to, so use the sfdisk partition
        # size in blocks (which assumes 512 byte block size)
        return 512 * self.normalized_sfdisk_dict['sfdisk_dict']['partitions'][long_device_node]['size']

    @staticmethod
    def parse_original_fstypes_output(original_fstypes_string):
        original_fstypes_dict = collections.OrderedDict([])
        for line in original_fstypes_string.splitlines():
            split_line = line.split(" ")
            if len(split_line) > 0:
                long_dev_node = split_line[0]
                if len(split_line) > 1:
                    original_fstypes_dict[long_dev_node] = {"filesystem": split_line[1].strip()}
        return original_fstypes_dict

    @staticmethod
    def parse_original_swapuuids_output(original_swapuuids_string):
        original_swapuuids_dict = collections.OrderedDict([])
        for line in original_swapuuids_string.splitlines():
            split_line = line.split(" ")
            if len(split_line) > 0:
                partition_number = int(split_line[0])
                if len(split_line) > 1:
                    original_swapuuids_dict[partition_number] = split_line[1]
        return original_swapuuids_dict
