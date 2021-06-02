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
import glob
import os
from os.path import dirname

import utility
from parser.fogproject_image import FogProjectImage
from parser.foxclone_image import FoxcloneImage
from parser.metadata_only_image import MetadataOnlyImage
from utility import Utility
from wizard_state import QEMU_NBD_NBD_DEVICE


# https://qemu.readthedocs.io/en/latest/tools/qemu-nbd.html
class QemuImage(MetadataOnlyImage):
    SUPPORTED_EXTENSIONS = {
        # ".iso" files take too long to be processed by qemu-nbd.
        "RAW": [".dd", ".img"],
        "VirtualBox": [".vdi"],
        "VMWare": [".vhd", ".vmdk"],
        "Hyper-V": [".vhdx", ".vhd"],
        "QEMU": [".qcow2", ".qcow", ".qed"],
        "Apple DMG": [".dmg"],
        "Parallels": [".hds", ".hdd", ".fdd"]
    }

    @staticmethod
    def is_supported_extension(filename):
        # https://fileinfo.com/filetypes/disk_image
        # https://qemu-project.gitlab.io/qemu/system/images.html


        # Ignore [/mnt/backup]/sbin/partclone.dd
        if filename.lower().endswith("partclone.dd"):
            return False, ""

        # Don't match on Redo Rescue images, which have filenames such as "20210307_sda1_001.img"
        m = utility.REMatcher(filename)
        if m.match(r".*_\d\d\d\.img"):
            return False, ""

        for key in QemuImage.SUPPORTED_EXTENSIONS.keys():
            for extension in QemuImage.SUPPORTED_EXTENSIONS[key]:
                if filename.lower().endswith(extension):
                    return True, extension
        return False, ""

    # The ".img" extension is also by FOG Project, Foxclone and Redo Rescue, so to prevent misleading entries, check
    # when Rescuezilla
    # TODO: Make this more efficient
    @staticmethod
    def has_conflict_img_format_in_same_folder(absolute_file_path, suffix_key):
        candidate_qemu_folder = dirname(absolute_file_path)
        if suffix_key != ".img":
            return False
        else:
            fog_project_glob = glob.glob(os.path.join(candidate_qemu_folder, "*.partitions"))
            foxclone_glob = glob.glob(os.path.join(candidate_qemu_folder, "*.backup"))
            redo_glob = glob.glob(os.path.join(candidate_qemu_folder, "*.redo"))
            if len(fog_project_glob) != 0 or len(foxclone_glob) != 0 or len(redo_glob) != 0:
                return True
        return False

    @staticmethod
    def does_file_extension_refer_to_raw_image(absolute_path):
        raw_list = QemuImage.SUPPORTED_EXTENSIONS['RAW']
        for key in raw_list:
            if absolute_path.endswith(key):
                return True
        return False

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

    def __init__(self, absolute_qemu_img_path, enduser_filename, timeout_seconds):
        self.has_initialized = False
        self.absolute_path = absolute_qemu_img_path
        self.timeout_seconds = timeout_seconds
        # Will be overwritten by superclass
        self.enduser_filename = enduser_filename
        self.warning_dict = {}

        qemu_img_cmd_list = ["qemu-img", "info", absolute_qemu_img_path]
        process, flat_command_string, fail_description = Utility.run("qemu-img info", qemu_img_cmd_list, use_c_locale=True)
        if process.returncode != 0:
            self.warning_dict[flat_command_string] = process.stderr
            return
        self.qemu_img_dict = QemuImage.parse_qemu_img_info(process.stdout)
        # Could use self.qemu_img_dict['disk size'], but getting from block device is preferable.

        is_associated, failed_message = self.associate_nbd(QEMU_NBD_NBD_DEVICE)
        if not is_associated:
            self.warning_dict[flat_command_string] = "Could not associate: " + failed_message
            return

        super().__init__(QEMU_NBD_NBD_DEVICE, absolute_qemu_img_path, enduser_filename)
        # Overwrite the image format.
        self.image_format = "QEMU_FORMAT"

        is_success, failed_message = QemuImage.deassociate_nbd(QEMU_NBD_NBD_DEVICE)
        if not is_success:
            self.warning_dict[flat_command_string] = failed_message
            return
        self.has_initialized = True

    def associate_nbd(self, nbd_device):
        is_success, error_message = self.deassociate_nbd(nbd_device)
        if not is_success:
            return False, error_message
        self.long_device_node = nbd_device
        is_raw_img = QemuImage.does_file_extension_refer_to_raw_image(self.absolute_path)
        if not is_raw_img:
            # Does NOT associate images read-only to provide the ability to ntfsfix partitions as the standard
            # Clonezilla behavior is to eg, run ntfsfix during a restore to fix common NTFS issues including
            # detecting hibernated NTFS partitions.
            qemu_nbd_cmd_list = ["qemu-nbd", "--connect=" + nbd_device, self.absolute_path]
        else:
            # Specifies raw format so qemu-nbd doesn't provide a non-zero error code. Read-only for safety.
            qemu_nbd_cmd_list = ["qemu-nbd", "--read-only", "--format=raw", "--connect=" + nbd_device, self.absolute_path]
        is_success, message = Utility.retry_run(short_description="qemu-nbd associate with " + nbd_device,
                          cmd_list=qemu_nbd_cmd_list,
                          expected_error_msg="Unexpected end-of-file",
                          retry_interval_seconds=1,
                          timeout_seconds=self.timeout_seconds)

        if is_success:
            # Keep probing using blkid until NBD device is ready.
            blkid_cmd_list = ["blkid", nbd_device]
            is_success, message = Utility.retry_run(short_description="Run blkid until NBD device ready " + nbd_device,
                              cmd_list=blkid_cmd_list,
                              expected_error_msg="",
                              retry_interval_seconds=1,
                              timeout_seconds=self.timeout_seconds)
        return is_success, message

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
