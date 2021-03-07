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
import time
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path

# https://qemu.readthedocs.io/en/latest/tools/qemu-nbd.html
import utility
from parser.parted import Parted
from parser.sfdisk import Sfdisk
from utility import Utility
from wizard_state import QEMU_NBD_NBD_DEVICE


class QemuImage:
    @staticmethod
    def is_supported_extension(filename):
        # https://fileinfo.com/filetypes/disk_image
        # https://qemu-project.gitlab.io/qemu/system/images.html
        supported_extensions = {
                                # The ".img" extension is not listed because it's also used by FOG Project and
                                # Foxclone, which causes misleading entries when Rescuezilla scans it as a raw
                                # uncompressed image.
                                # Also not listed ".iso" .extension because the value add for ISO9660 ISOs is low
                                # and the scan takes time.
                                "RAW": [".dd"],
                                "VirtualBox": [".vdi"],
                                "VMWare": [".vhd", ".vmdk"],
                                "Hyper-V": [".vhdx", ".vhd"],
                                "QEMU": [".qcow2", ".qcow", ".qed"],
                                "Apple DMG": [".dmg"],
                                "Parallels": [".hds", ".hdd", ".fdd"]
        }
        # Don't match on Redo Rescue images, which have filenames such as "20210307_sda1_001.img"
        m = utility.REMatcher(filename)
        if m.match(r".*_\d\d\d\.img"):
            return False

        for key in supported_extensions.keys():
            for extension in supported_extensions[key]:
                if filename.lower().endswith(extension):
                    return True
        return False

    def __init__(self, absolute_qemu_img_path, enduser_filename, timeout_seconds):
        self.timeout_seconds = timeout_seconds
        self.image_format = "QEMU_FORMAT"
        self.absolute_path = absolute_qemu_img_path
        self.enduser_filename = enduser_filename
        self.warning_dict = {}

        statbuf = os.stat(self.absolute_path)
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(statbuf.st_mtime))

        print("Last modified timestamp " + self.last_modified_timestamp)

        dir = Path(absolute_qemu_img_path).parent.as_posix()
        print("Qemu directory : " + dir)

        self.short_device_node_partition_list = []
        self.short_device_node_disk_list = []
        self.lvm_vg_dev_dict = {}
        self.lvm_logical_volume_dict = {}
        self.dev_fs_dict = {}
        self.size_bytes = 0
        self.enduser_readable_size = ""
        self.is_needs_decryption = False
        self.sfdisk_dict = {'partitions': {}}
        self.parted_dict = {'partitions': {}}

        qemu_img_cmd_list = ["qemu-img", "info", absolute_qemu_img_path]
        process, flat_command_string, fail_description = Utility.run("qemu-img info", qemu_img_cmd_list, use_c_locale=True)
        if process.returncode != 0:
            self.warning_dict[flat_command_string] = process.stderr
            return
        self.qemu_img_dict = QemuImage.parse_qemu_img_info(process.stdout)
        self.enduser_readable_size = self.qemu_img_dict['disk size']

        is_associated, failed_message = self.associate_nbd(QEMU_NBD_NBD_DEVICE)
        if not is_associated:
            self.warning_dict[flat_command_string] = "Could not associate: " + failed_message
            return

        process, flat_command_string, failed_message = Utility.run("Get partition table", ["sfdisk", "--dump", QEMU_NBD_NBD_DEVICE], use_c_locale=True)
        if process.returncode != 0:
            self.warning_dict[flat_command_string] = "Could not extract partition table: " + process.stderr
            # Not returning here so can disconnect.
        else:
            # TOOD: Could use sfdisk's JSON output here.
            self.sfdisk_dict = Sfdisk.parse_sfdisk_dump_output(process.stdout)

        parted_process, flat_command_string, failed_message = Utility.run("Get filesystem information",
                                                          ["parted", "--script", QEMU_NBD_NBD_DEVICE, "unit", "s",
                                                           "print"], use_c_locale=True)
        if process.returncode != 0:
            self.warning_dict[flat_command_string] = "Could not extract filesystem: " + process.stderr
            # Not returning here so can disconnect.
        else:
            self.parted_dict = Parted.parse_parted_output(parted_process.stdout)

        is_success, failed_message = QemuImage.deassociate_nbd(QEMU_NBD_NBD_DEVICE)
        if not is_success:
            self.warning_dict[flat_command_string] = failed_message
            return

    def associate_nbd(self, nbd_device):
        is_associated = False

        num_tries = 0
        retry_interval_seconds = 1
        max_tries = self.timeout_seconds / retry_interval_seconds
        # The qemu-nbd command often fails with "Disconnect client, due to: Unexpected end-of-file before all bytes
        # were read". The root cause is how NBD is handled in the kernel, apparently. So keep retrying until it connects
        while not is_associated and num_tries < max_tries:
            num_tries += 1

            is_success, error_message = self.deassociate_nbd(nbd_device)
            if not is_success:
                return False, error_message

            qemu_nbd_cmd_list = ["qemu-nbd", "--read-only", "--connect=" + nbd_device, self.absolute_path]
            process, flat_command_string, fail_description = Utility.run("qemu-nbd associate with " + nbd_device, qemu_nbd_cmd_list, use_c_locale=True)
            if process.returncode != 0:
                error_message = process.stderr
                if "Unexpected end-of-file" in process.stderr:
                    # Expecting a lot of "Disconnect client, due to: Unexpected end-of-file before all bytes were read"
                    time.sleep(retry_interval_seconds)
                else:
                    # If the error message was unexpected, return immediately
                    return False, error_message
            else:
                return True, ""
        return False, "timeout exceeded"

    @staticmethod
    def deassociate_nbd(nbd_device):
        # In practice the partprobe refresh partition table seems to hang unless an nbd-client disconnection is also
        # done
        process, flat_command_string, failed_description = Utility.run("Disconnect nbd association",
                                                                   ["nbd-client", "-disconnect",
                                                                    nbd_device],
                                                                   use_c_locale=True)
        if process.returncode != 0:
            return False, failed_description

        qemu_nbd_disconnect_cmd_list = ["qemu-nbd", "--disconnect", nbd_device]
        process, flat_command_string, fail_description = Utility.run("qemu-nbd request disconnect " + nbd_device,
                                                                     qemu_nbd_disconnect_cmd_list,
                                                                     use_c_locale=True)
        if process.returncode != 0:
            return False, fail_description

        return True, ""

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for long_device_node in self.sfdisk_dict['partitions'].keys():
            base_device_node, partition_number = Utility.split_device_string(long_device_node)
            flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(long_device_node) + ") "
            index += 1
        return flat_string

    def has_partition_table(self):
        # Temp
        return True

    def flatten_partition_string(self, long_device_node):
        flat_string = ""
        fs = self._get_human_readable_filesystem(long_device_node)
        if fs != "":
            flat_string = fs + " "
        partition_size_bytes = self.sfdisk_dict['partitions'][long_device_node]['size'] * 512
        flat_string += Utility.human_readable_filesize(partition_size_bytes)
        return flat_string

    def _get_human_readable_filesystem(self, long_device_node):
        # Prefer estimated size from parted partition table backup, but this requires splitting the device node
        image_base_device_node, image_partition_number = Utility.split_device_string(long_device_node)
        if image_partition_number in self.parted_dict['partitions'].keys():
            return self.parted_dict['partitions'][image_partition_number]['filesystem']

    @staticmethod
    def parse_qemu_img_info(qemu_img_info_string):
        qemu_img_info_dict = {}
        lines = qemu_img_info_string.splitlines()
        for line in lines:
            split = line.split(":")
            key = split[0].strip()
            value = split[1].strip()
            qemu_img_info_dict[key] = value
        return qemu_img_info_dict

