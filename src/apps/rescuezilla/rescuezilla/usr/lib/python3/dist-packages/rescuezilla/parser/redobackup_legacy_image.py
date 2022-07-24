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
import glob
import os
import re

from babel.dates import format_datetime

from parser.partclone import Partclone
from parser.sfdisk import Sfdisk
from utility import Utility, _


# Background: Redo Backup and Recovery has a complicated version history: it was originally actively developed
# between 2010-2012 before being abandoned by the original author, with some intrepid users of Redo Backup
# Sourceforge forum creating several forks [1]. Each of the forks have their own quirks and bugs.
#
# To unify all the Redo Backup and Recovery forks under the Rescuezilla banner, and provide the best end-user
# experience, all Redo Backup and Recovery formats are supported.
#
# Redo Backup and Recovery only supported /dev/sdX device nodes, and Rescuezilla 1.0.5 images supported /dev/sdX and
# /dev/nvmeAnBp3 nodes
#
# [1] https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#identifying-redo-backup-versions
class RedoBackupLegacyImage:
    def __init__(self, absolute_path, enduser_filename, filename):
        # Redo Backup images never need decryption
        self.is_needs_decryption = False
        self.absolute_path = absolute_path
        self.enduser_filename = enduser_filename
        print("Reading backup : " + absolute_path)
        dirname = os.path.dirname(absolute_path)
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

        self.compression = "gzip"
        if filename.endswith(".redo"):
            prefix = filename.split(".redo")[0]
            print("prefix: " + prefix)
            self.compression = "uncompressed"
            self.image_format = "REDOBACKUP_0.9.2_FORMAT"
        elif filename.endswith(".backup"):
            prefix = filename.split(".backup")[0]
            print("prefix: " + prefix)
            rescuezilla_version_abs_path = os.path.join(dirname, prefix + ".rescuezilla.backup_version")
            if not os.path.exists(rescuezilla_version_abs_path):
                self.image_format = "REDOBACKUP_0.9.3_1.0.4_FORMAT"
            else:
                self.image_format = "RESCUEZILLA_1.0.5_FORMAT"
                self.rescuezilla_version = Utility.read_file_into_string(rescuezilla_version_abs_path).strip()
                print("Backup originally created with Rescuezilla version: " + self.rescuezilla_version)
        else:
            raise ValueError("Expected Rescuezilla backup to end with .backup: " + absolute_path)

        self.last_modified_timestamp = format_datetime(os.stat(absolute_path).st_mtime)
        print("Last modified timestamp " + self.last_modified_timestamp)

        self.short_device_node_partition_list = Utility.read_linebreak_delimited_file_into_list(absolute_path)
        print("Source_partitions: " + str(self.short_device_node_partition_list))

        self.size_bytes = int(Utility.read_file_into_string(os.path.join(dirname, prefix + ".size").strip()))
        print("Size: " + str(self.size_bytes))
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))

        self._mbr_absolute_path = os.path.join(dirname, prefix + ".mbr")
        # Get the size of the MBR image because a Sourceforge user named chcatzsf released two unofficial
        # German-language Redo Backup and Recovery update based on Ubuntu 13.10 and Ubuntu 14.04. These two versions
        # incorrectly created 512 byte Master Boot Record backup images. More information [1].
        #
        # [1] https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in-chcatzsfs-ubuntu-1310-and-1404-releases-german-language-only
        self.mbr_size = int(os.stat(self._mbr_absolute_path).st_size)
        if self.mbr_size == 512:
            # Two popular unofficial Redo Backup v1.0.4 updates by Sourceforge user chcatzsf
            # have major bugs where bootloaders like GRUB are not not fully backed up, so Linux-based operating
            # cannot boot after a restore. This bug only affected those two updates (German-language only) and the
            # problem can be fixed with careful manual intervention.
            # Full details in:
            # https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in
            # -chcatzsfs-ubuntu-1310-and-1404-releases-german-language-only
            self.warning_dict[enduser_filename] = _("The backup's bootloader data is shorter than expected. If the backup contained certain bootloaders like GRUB, during a restore operation Rescuezilla will try and re-install the bootloader.")

        sfdisk_absolute_path = os.path.join(dirname, prefix + ".sfdisk")
        self.normalized_sfdisk_dict = Sfdisk.generate_normalized_sfdisk_dict(sfdisk_absolute_path, self)
        if not self.image_format == "RESCUEZILLA_1.0.5_FORMAT":
            self.normalized_sfdisk_dict['prefer_old_sfdisk_binary'] = True

        # Cannot rely on sfdisk drive name due to some Redo Backup versions not populating this file correctly.
        if 'device' in self.normalized_sfdisk_dict['sfdisk_dict'].keys():
            self.short_device_node_disk_list = [self.normalized_sfdisk_dict['sfdisk_dict']['device']]
        else:
            self.short_device_node_disk_list = ["unknown"]

        # The NVMe drive handling on Rescuezilla v1.0.5.1+ set the drive name in the .backup file start with "sdz" to
        # preserve the ability to restore with older versions of Rescuezilla (which read the source drive). Since v2.0,
        # this string is used as a key into sfdisk partitions, so the ".backup" partition list such containing elements
        # like "sdz3" needs to be renamed to eg, "nvme0n1p3" here to preserve full backwards compatibility.
        if 'partitions' in self.normalized_sfdisk_dict['sfdisk_dict'].keys() and len(self.normalized_sfdisk_dict['sfdisk_dict']['partitions'].keys()) > 1:
            # Long drive node extracted from sfdisk dictionary
            sfdisk_long_drive_node = list(self.normalized_sfdisk_dict['sfdisk_dict']['partitions'].keys())[0]
            actual_base_device_node, first_partition_number = Utility.split_device_string(sfdisk_long_drive_node)
            for i in range(len(self.short_device_node_partition_list)):
                node_to_potentially_rename = self.short_device_node_partition_list[i]
                if node_to_potentially_rename.startswith("sdz") and actual_base_device_node != "sdz":
                    # This node is renamed, and the list is updated.
                    fake_base_device_node, actual_partition_number = Utility.split_device_string(node_to_potentially_rename)
                    corrected_long_device_node = Utility.join_device_string(actual_base_device_node, actual_partition_number)
                    corrected_short_device_node = re.sub('/dev/', '', corrected_long_device_node)
                    self.short_device_node_partition_list[i] = corrected_short_device_node

        self.partclone_info_dict_dict = collections.OrderedDict([])
        self.image_format_dict_dict = collections.OrderedDict([])
        # All Rescuezilla v1.0.5 and Redo Backup and Recovery images use gzip compression EXCEPT the uncompressed v0.9.2
        compression = "gzip"
        for short_device_node in self.short_device_node_partition_list:
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            if self.image_format == "REDOBACKUP_0.9.2_FORMAT":
                # Redo Backup v0.9.2 are *not* split
                image_match_string = os.path.join(dirname, prefix + "_part" + str(partition_number))
                # ... and not compressed
                compression = "uncompressed"
            else:
                # Redo Backup v0.9.3-v1.0.4 and Rescuezilla v1.0.5 images are split up, eg "20200901_part2.000".
                # However need to be careful because Rescuezilla's backup directory contains a log files
                # eg, "20200901_part2_partclone.log", so the dot character before the asterisk is important. It prevents
                # the underscore from matching.
                image_match_string = os.path.join(dirname, prefix + "_part" + str(partition_number) + ".*")
            # Get absolute path partition images. Eg, [/path/to/20200813_part3.000, /path/to/20200813_part3.001 etc]
            abs_partclone_image_list = glob.glob(image_match_string)
            # Sort by alphabetical sort. Lexical sort not required here because fixed number of digits (so no risk
            # of "1, 10, 2, 3" issues)
            abs_partclone_image_list.sort()
            if len(abs_partclone_image_list) == 0:
                # The legacy Redo Backup and Recovery format cannot distinguish between failed partclone backup and a
                # user who chose not to backup a partition
                self.warning_dict[short_device_node] = _("Cannot find partition's associated partclone image") + " " + Utility.get_cannot_distinguish_msg()
                self.image_format_dict_dict[short_device_node] = {'type': "missing",
                                                                  'prefix': short_device_node,
                                                                  'estimated_size_bytes': 0,
                                                                  'is_lvm_logical_volume': False}
                continue

            command = "partclone"
            filesystem = "<unknown>"
            # Rescuezilla v1.0.5 format creates partition to filesystem mapping files
            command_filepath = os.path.join(dirname, prefix + ".partclone.command.part" + str(partition_number))
            if os.path.isfile(command_filepath):
                command = Utility.read_file_into_string(command_filepath).strip()
                print(str(short_device_node) + ": " + command)
                restore_binary = command
                filesystem = re.sub('partclone.', '', restore_binary)

            use_old_partclone = False
            # Use partclone.info to extract filesystem and size information from the image files. This is a time
            # consuming operation but Redo 0.9.3-1.0.4 images benefit from this.
            # Rescuezilla 1.0.5 format has a backup of the filesystem (from the restore_command files), and the size (
            # from sfdisk)
            if self.image_format == "REDOBACKUP_0.9.3_1.0.4_FORMAT" or self.image_format == "REDOBACKUP_0.9.2_FORMAT":
                use_old_partclone = True
                self.partclone_info_dict_dict[short_device_node] = Partclone.get_partclone_info_dict(abs_partclone_image_list, short_device_node, compression)
                filesystem = self.partclone_info_dict_dict[short_device_node]['filesystem'].lower()
                print(str(self.partclone_info_dict_dict))
            if filesystem != "<unknown>" and filesystem != "raw":
                self.image_format_dict_dict[short_device_node] = {'type': "partclone",
                                                                 'absolute_filename_glob_list': abs_partclone_image_list,
                                                                 'compression': compression,
                                                                 'filesystem': filesystem,
                                                                 'binary': "partclone." + filesystem,
                                                                 "prefix": prefix,
                                                                 'use_old_partclone': use_old_partclone,
                                                                 'is_lvm_logical_volume': False}
            else:
                self.image_format_dict_dict[short_device_node] = {'type': "dd",
                                                                 'absolute_filename_glob_list': abs_partclone_image_list,
                                                                 'compression': compression,
                                                                 'binary': "partclone.dd",
                                                                 'filesystem': filesystem,
                                                                 "prefix": prefix,
                                                                 'use_old_partclone': use_old_partclone,
                                                                 'is_lvm_logical_volume': False}

            # Compute the partition size estimate, and save it to avoid recomputing.
            self.image_format_dict_dict[short_device_node]['estimated_size_bytes'] = self._compute_partition_size_byte_estimate(short_device_node)

    def does_image_key_belong_to_device(self, image_format_dict_key):
        return True

    def has_partition_table(self):
        # All Redo Backup legacy images have at least the MBR file, even if the sfdisk file is empty or the MBR itself
        # is truncated to 512 bytes.
        #
        # For completeness it's noted creating a backup of a filesystem directly on a disk using Redo Backup v0.9.2
        # creates some files, including the MBR and .redo file (but no populatd filesystem images).
        return True

    def get_absolute_mbr_path(self):
        return self._mbr_absolute_path

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for short_device_node in self.short_device_node_partition_list:
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(short_device_node) + ") "
            index += 1
        return flat_string

    def flatten_partition_string(self, short_device_node):
        flat_string = self._get_human_readable_filesystem(short_device_node) + " "
        partition_size_bytes = self.image_format_dict_dict[short_device_node]['estimated_size_bytes']
        flat_string += Utility.human_readable_filesize(partition_size_bytes)
        return flat_string

    def _get_human_readable_filesystem(self, short_device_node):
        base_device_node, partition_number = Utility.split_device_string(short_device_node)
        if short_device_node in self.image_format_dict_dict.keys() and 'filesystem' in self.image_format_dict_dict[short_device_node].keys():
            return self.image_format_dict_dict[short_device_node]['filesystem']
        else:
            print(self.absolute_path + ": Unable to use " + str(partition_number) + " from " + short_device_node + " in " + str(self.partclone_info_dict_dict) + " or " + str(self.partclone_info_dict_dict))
            return "NOT_FOUND "

    # Estimates size of each filesystem image, ideally based on the partition table, but otherwise by querying the total
    # number of bytes used by the image files. Does NOT use partclone.info, which too slow to run on every image.
    def _compute_partition_size_byte_estimate(self, short_device_node):
        estimated_size = 0
        base_device_node, partition_number = Utility.split_device_string(short_device_node)
        # Convert short device node to long device node by prepending "/dev/" (this simply approach is only correct for
        # Rescuezilla 1.0.5 and Redo Backup and Recovery images, as the format never supported multipath device nodes.
        long_device_node = "/dev/" + short_device_node
        # Not all images can have partclone.info run on them (eg. dd images), nor would we want to because scanning is
        # slow. But use the filesystem size from partclone.info, when available:
        if short_device_node in self.partclone_info_dict_dict.keys() and 'size' in self.partclone_info_dict_dict[
            short_device_node].keys():
            estimated_size = self.partclone_info_dict_dict[short_device_node]['size']['bytes']
        # Not all legacy Redo Backup images are guaranteed to have partition table.
        elif 'partitions' in self.normalized_sfdisk_dict['sfdisk_dict'].keys() and long_device_node in self.normalized_sfdisk_dict['sfdisk_dict']['partitions'].keys():
            # Otherwise, get the partition size from sfdisk partition table.
            estimated_size = self.normalized_sfdisk_dict['sfdisk_dict']['partitions'][long_device_node]['size'] * 512

        # Some older sfdisk partition table backups incorrectly have size of 0.
        if estimated_size == 0:
            # Not all compressed images can be queried for uncompressed size (eg, gzip). So worst-case get the size
            # from the compressed split image size (which is 0 bytes if the file is missing).
            return Utility.count_total_size_of_files_on_disk(self.image_format_dict_dict[short_device_node]['absolute_filename_glob_list'], "gzip")

        return estimated_size
