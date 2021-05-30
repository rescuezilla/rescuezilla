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
import os
import pprint
import re
import time
from datetime import datetime
from pathlib import Path

from babel.dates import format_datetime

import utility
from utility import Utility


# The handling of FSArchiver images is not derived from the FSArchiver source code, but has been implemented purely
# based on examining the images generated from using qt-fsarchiver and the fsarchiver command-line program.
# Any errors in parsing here are Rescuezilla's own.
class FsArchiverImage:
    def __init__(self, absolute_fsarchiver_fsa_path, enduser_filename, filename):
        self.image_format = "FSARCHIVER_FORMAT"
        self.absolute_path = absolute_fsarchiver_fsa_path
        self.enduser_filename = enduser_filename
        self.fsa_dict = {'filesystems': {}}
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

        # TODO: Remove the need for this
        self.short_device_node_disk_list = ["unknown"]

        dir = Path(absolute_fsarchiver_fsa_path).parent.as_posix()
        print("FSArchiver directory : " + dir)

        prefix = filename.split(".fsa")[0]
        print("prefix: " + prefix)
        dirname = os.path.dirname(absolute_fsarchiver_fsa_path)

        # The qt-fsarchiver frontend is able to save notes/description to a TXT file.
        qt_fsarchiver_notes_abs_path = os.path.join(dirname, prefix + ".txt")
        if os.path.exists(qt_fsarchiver_notes_abs_path):
            self.user_notes = Utility.read_file_into_string(qt_fsarchiver_notes_abs_path)

        # Use `fsarchiver archinfo <fsa path>` to determine if the archive is encrypted
        self.is_needs_decryption = False
        dirname = os.path.dirname(absolute_fsarchiver_fsa_path)
        fsarchiver_archinfo_cmd_list = ["fsarchiver", "archinfo", absolute_fsarchiver_fsa_path]
        process, flat_command_string, fail_description = Utility.run("fsarchiver archinfo", fsarchiver_archinfo_cmd_list, use_c_locale=True)
        if process.returncode == 0:
            # Process the archive information
            self.fsa_dict = FsArchiverImage.parse_fsarchiver_archinfo_output(process.stderr)
            print("Processed: " + str(self.fsa_dict))
        else:
            self.last_modified_timestamp = format_datetime(datetime.fromtimestamp((os.stat(absolute_fsarchiver_fsa_path).st_mtime)))
            self.size_bytes = Utility.count_total_size_of_files_on_disk([absolute_fsarchiver_fsa_path], "unknown")
            # Covert size in bytes to KB/MB/GB/TB as relevant
            self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))
            if "password" in process.stderr:
                print("Image is encrypted.")
                # Found an encrypted image. Populate the only fields we can.
                self.is_needs_decryption = True
            self.warning_dict['archinfo'] = "Unable to process FSArchiver" + process.stdout + " " + process.stderr
            return

        pp = pprint.PrettyPrinter(depth=6)
        pp.pprint(self.fsa_dict)

        with Utility.setlocale('C'):
            # Convert FSArchiver's English human-readable string to Python datetime
            fsarchiver_datetime = datetime.strptime(self.fsa_dict['date'], "%Y-%m-%d_%H-%M-%S")
        # Convert to a string that's consistent with the rest of Rescuezilla
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(fsarchiver_datetime.timestamp()))
        print("Last modified timestamp " + self.last_modified_timestamp)

        self.size_bytes = 0
        for fs_key in self.fsa_dict['filesystems'].keys():
            self.size_bytes += self.fsa_dict['filesystems'][fs_key]['size_bytes']
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))

    def has_partition_table(self):
        # Some FSArchiver images have a PBR backup, but there's no consistent MBR backup.
        return False

    def get_absolute_mbr_path(self):
        return None

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for fs_key in self.fsa_dict['filesystems'].keys():
            flat_string += "(" + fs_key + ": " + self.flatten_partition_string(fs_key) + ") "
            index += 1
        return flat_string

    def flatten_partition_string(self, fs_key):
        flat_string = ""
        fs = self.fsa_dict['filesystems'][fs_key]['filesystem_format']
        size_bytes = self._compute_partition_size_byte_estimate(fs_key)
        flat_string += str(fs) + " " + Utility.human_readable_filesize(size_bytes)
        return flat_string

    def _compute_partition_size_byte_estimate(self, fs_key):
        return self.fsa_dict['filesystems'][fs_key]['size_bytes']

    # FSArchiver images are usually just one file.
    #
    # The qt-fsarchiver frontend produces a .txt file too, for human-readability and for notes/description. It also
    # can make a PBR backup etc.
    #
    # Because the FSArchiver backup itself is a single file image, the metadata is expected to be extracted from the
    # image itself using `fsarchiver archinfo file.fsa`.
    #
    # See unit test for worked example.
    @staticmethod
    def parse_fsarchiver_archinfo_output(fsarchiver_archinfo_output):
        # Encrypted:
        # oper_restore.c#1158,extractar_read_mainhead(): you have to provide the password which was used to create archive, no password given on the command line
        fsarchiver_archinfo_dict = {'filesystems': {}}
        # Handle metadata:
        initial_split = re.split("=*\sfilesystem information\s=*", fsarchiver_archinfo_output)
        for line in initial_split[0].splitlines():
            try:
                split = re.split(":", line)
                key = split[0].strip()
                if key == "" or "archive information" in key:
                    # Empty lines to be expected, and heading line expected too.
                    continue
                value = split[1].strip()
                if key == "Archive type":
                    fsarchiver_archinfo_dict['archive_type'] = value
                elif key == "Filesystems count":
                    fsarchiver_archinfo_dict['fs_count'] = int(value)
                elif key == "Archive id":
                    fsarchiver_archinfo_dict['archive_id'] = value
                elif key == "Archive file format":
                    fsarchiver_archinfo_dict['archive_file_format'] = value
                elif key == "Archive created with":
                    fsarchiver_archinfo_dict['created_with'] = value
                elif key == "Archive creation date":
                    fsarchiver_archinfo_dict['date'] = value
                elif key == "Archive label":
                    fsarchiver_archinfo_dict['archive_label'] = value
                elif key == "Minimum fsarchiver version":
                    fsarchiver_archinfo_dict['minimum_fsarchiver_version'] = value
                elif key == "Compression level":
                    fsarchiver_archinfo_dict['compression_level'] = value
                elif key == "Encryption algorithm":
                    fsarchiver_archinfo_dict['encryption_algorithm'] = value
                else:
                    print("Unknown key" + key)
            except IndexError:
                print("Unable to parse: " + str(line) + ". Skipping")

        # Loop over each filesystem information section, line by line
        for block_string in initial_split[1:]:
            for line in block_string.splitlines():
                # print("Processing fsarchiver_archinfo line: " + str(line))
                try:
                    split = re.split(":", line)
                    key = split[0].strip()
                    if key == "":
                        # Empty lines to be expected
                        continue
                    value = split[1].strip()
                    if key == "Filesystem id in archive":
                        # Treating fs_key as a string (rather than an int) for consistency with the rest of Rescuezilla.
                        fs_key = value
                        fsarchiver_archinfo_dict['filesystems'][fs_key] = {}
                    elif key == "Filesystem format":
                        fsarchiver_archinfo_dict['filesystems'][fs_key]['filesystem_format'] = value
                    elif key == "Filesystem label":
                        fsarchiver_archinfo_dict['filesystems'][fs_key]['filesystem_label'] = value
                    elif key == "Filesystem uuid":
                        fsarchiver_archinfo_dict['filesystems'][fs_key]['filesystem_uuid'] = value
                    elif key == "Original device":
                        fsarchiver_archinfo_dict['filesystems'][fs_key]['original_long_device_node'] = value
                    elif key == "Original filesystem size":
                        fsarchiver_archinfo_dict['filesystems'][fs_key]['size_bytes'] = FsArchiverImage.extract_bytes_from_string(value)
                    elif key == "Space used in filesystem":
                        fsarchiver_archinfo_dict['filesystems'][fs_key]['used_bytes'] = FsArchiverImage.extract_bytes_from_string(value)
                    else:
                        print("Unknown key" + key)
                except IndexError:
                    print("Unable to parse: " + str(line) + ". Skipping")

        return fsarchiver_archinfo_dict

    # Given a string "458.09 MB (480337920 bytes)", return 480337920.
    @staticmethod
    def extract_bytes_from_string(value):
        m = utility.REMatcher(value)
        if m.match(r"^.*\(([0-9]*) bytes\).*$"):
            return int(m.group(1))
        else:
            return 0