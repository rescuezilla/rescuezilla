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
import json
import os
import pprint
import re
import tempfile
from datetime import datetime
from email.utils import format_datetime

from babel.dates import format_datetime

from parser.blkid import Blkid
from parser.clonezilla_image import ClonezillaImage
from parser.combined_drive_state import CombinedDriveState
from parser.os_prober import OsProber
from parser.parted import Parted
from parser.sfdisk import Sfdisk
from utility import Utility

# MetadataOnlyImage contains the data like sfdisk partition table, post-MBR gap, EBR backup, but (unlike ClonezillaImage
# and FoxcloneImage) does not contain the paths to partclone files but instead points to the source partition dev nodes.
# This is useful for cloning (device-to-device mode) and also restoring QemuImages.
class MetadataOnlyImage:
    def __init__(self, partition_long_device_node, absolute_path=None, enduser_filename=None):
        self.image_format = "METADATA_ONLY_FORMAT"
        self.long_device_node = partition_long_device_node
        if absolute_path is None:
            self.absolute_path = partition_long_device_node
        else:
            self.absolute_path = absolute_path

        if enduser_filename is None:
            self.absolute_path = partition_long_device_node
        else:
            self.enduser_filename = enduser_filename
        self.normalized_sfdisk_dict = {'absolute_path': None, 'sfdisk_dict': {'partitions': {}}, 'file_length': 0}
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
        self._mbr_absolute_path = None

        statbuf = os.stat(self.absolute_path)
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(statbuf.st_mtime))
        print("Last modified timestamp " + self.last_modified_timestamp)

        process, flat_command_string, failed_message = Utility.run("Get partition table", ["sfdisk", "--dump", partition_long_device_node], use_c_locale=True)
        if process.returncode != 0:
            # Expect devices without a partition table to not be able to extract partition table
            print("Could not extract filesystem using sfdisk: " + process.stderr)
        else:
            sfdisk_string = process.stdout
            f = tempfile.NamedTemporaryFile(mode='w', delete=False)
            f.write(sfdisk_string)
            f.close()
            self.normalized_sfdisk_dict = Sfdisk.generate_normalized_sfdisk_dict(f.name, self)
        if 'device' in self.normalized_sfdisk_dict['sfdisk_dict'].keys():
            self.short_device_node_disk_list = [self.normalized_sfdisk_dict['sfdisk_dict']['device']]

        # Get the parted partition table. For convenience, using the bytes unit, not sectors.
        parted_process, flat_command_string, failed_message = Utility.run("Get filesystem information",
                                                          ["parted", "--script", partition_long_device_node, "unit", "b",
                                                           "print"], use_c_locale=True)
        if parted_process.returncode != 0:
            # Expect devices without a partition table to not be able to extract partition table
            print("Could not extract filesystem using parted: " + parted_process.stderr)
        self.parted_dict = Parted.parse_parted_output(parted_process.stdout)
        if len(self.short_device_node_disk_list) == 0 and 'long_dev_node' in self.parted_dict.keys():
            self.short_device_node_disk_list = [self.parted_dict['long_dev_node']]

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.parted_dict)

        lsblk_process, flat_command_string, failed_message = Utility.run("Querying device capacity",
                                                                         ["lsblk", "--getsize64", partition_long_device_node],
                                                                         use_c_locale=True)
        if lsblk_process.returncode != 0:
            # Expected for NBD device nodes
            print("Failed to get drive capacity from device node")

        # Create a CombinedDriveState structure for the MetadataOnlyImage, which may otherwise not be populated.
        lsblk_cmd_list = ["lsblk", "-o", "KNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL", "--paths", "--bytes",
                          "--json", self.long_device_node]
        process, flat_command_string, fail_description = Utility.run("lsblk", lsblk_cmd_list, use_c_locale=True)
        lsblk_json_dict = json.loads(process.stdout)

        # blkid is called in DriveQuery and without arugments it prints information about all *partitions* in the system
        # (eg, /dev/sda1, /dev/sda2), but not th base device. But with an argument, it only prints out the base device.
        # But globbing using an wildcard match prints out the base device *and* the partitions. Not ideal, but it works.
        partition_device_glob_list = glob.glob(self.long_device_node + "*")
        blkid_cmd_list = ["blkid"] + partition_device_glob_list
        process, flat_command_string, fail_description = Utility.run("blkid", blkid_cmd_list, use_c_locale=True)
        blkid_dict = Blkid.parse_blkid_output(process.stdout)

        # OS Prober takes too long to run
        os_prober_dict = {}

        self.drive_state = CombinedDriveState.construct_combined_drive_state_dict(lsblk_json_dict=lsblk_json_dict,
                                                                                  blkid_dict=blkid_dict,
                                                                                  osprober_dict=os_prober_dict,
                                                                                  parted_dict_dict={self.long_device_node:self.parted_dict},
                                                                                  sfdisk_dict_dict={self.long_device_node:self.normalized_sfdisk_dict})
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.drive_state)

        self.image_format_dict_dict = collections.OrderedDict([])
        total_size_estimate = 0
        drive_state_partitions_dict = self.drive_state[self.long_device_node]['partitions']
        for partition_long_device_node in drive_state_partitions_dict:
            if 'type' in drive_state_partitions_dict[partition_long_device_node].keys() \
                    and drive_state_partitions_dict[partition_long_device_node]['type'] == "extended":
                # Skip extended partitions as they will be handled by the '-ebr' file
                continue
            self.image_format_dict_dict[partition_long_device_node] = {'type': "raw",
                                                                       'compression': "uncompressed",
                                                                       'is_lvm_logical_volume': False,
                                                                       'filesystem': drive_state_partitions_dict[partition_long_device_node]['filesystem']}

        # Estimate the disk size from sfdisk partition table backup
        last_partition_key, last_partition_final_byte = Sfdisk.get_highest_offset_partition(self.normalized_sfdisk_dict)
        self.size_bytes = last_partition_final_byte
        if self.size_bytes == 0:
            self.size_bytes = self.parted_dict['capacity']
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))

    # The BackupManager, needs partition information (filesystems etc) in certain structure. Clonezilla combines
    # information from several different sources using what Rescuezilla called the 'CombinedDriveState'
    # But for MetadataOnlyImages, this may not be populated
    def get_partitions_to_backup(self, partition_list):
        partitions_to_backup = collections.OrderedDict()
        for key in partition_list:
            partitions_to_backup[key] = self.drive_state[self.long_device_node]['partitions'][key]
            partitions_to_backup[key]['description'] = self.flatten_partition_string(key)
        return partitions_to_backup

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for short_device_node in self.image_format_dict_dict.keys():
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(short_device_node) + ") "
            index += 1
        return flat_string

    def does_image_key_belong_to_device(self, image_format_dict_key):
        return True

    def has_partition_table(self):
        # Clonezilla images use presence of MBR file, here the partition table is considered present if there is
        # partitions in the image's sfdisk backup
        if len(self.normalized_sfdisk_dict['sfdisk_dict']['partitions']) > 0:
            return True
        else:
            return False

    def get_absolute_mbr_path(self):
        return self._mbr_absolute_path

    def flatten_partition_string(self, long_device_node):
        flat_string = ""
        fs = self._get_human_readable_filesystem(long_device_node)
        if fs != "" and fs is not None:
            flat_string = fs + " "
        partition_size_bytes = self._compute_partition_size_byte_estimate(long_device_node)
        flat_string += Utility.human_readable_filesize(partition_size_bytes)
        return flat_string

    def _compute_partition_size_byte_estimate(self, long_device_node):
        if long_device_node in self.normalized_sfdisk_dict['sfdisk_dict']['partitions'].keys():
            return self.normalized_sfdisk_dict['sfdisk_dict']['partitions'][long_device_node]['size'] * 512
        else:
            return self.size_bytes

    def _get_human_readable_filesystem(self, long_device_node):
        # Prefer estimated size from parted partition table backup, but this requires splitting the device node
        image_base_device_node, image_partition_number = Utility.split_device_string(long_device_node)
        if image_partition_number in self.parted_dict['partitions'].keys():
            return self.parted_dict['partitions'][image_partition_number]['filesystem']

    # FIXME: This function directly duplicates part of ClonezillaImage class
    # Does not use LVM on purpose.
    def scan_dummy_images_and_annotate(self, dir):
        # Loops over the partitions listed in the 'parts' file
        for image_key in self.image_format_dict_dict.keys():
            short_partition_key = re.sub('/dev/', '', image_key)
            # For standard MBR and GPT partitions, the partition key listed in the 'parts' file has a directly
            # associated backup image, so check for this.
            image_format_dict = ClonezillaImage.scan_backup_image(dir, short_partition_key, False)
            if len(image_format_dict) > 0:
                self.image_format_dict_dict[image_key].update(image_format_dict)
            else:
                # Expected for eg, extended partition.
                print("Could not find " + short_partition_key + " in " + dir)
