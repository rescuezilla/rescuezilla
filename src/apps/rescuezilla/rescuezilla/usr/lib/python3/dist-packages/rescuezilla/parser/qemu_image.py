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

import utility
from parser.metadata_only_image import MetadataOnlyImage
from utility import Utility
from wizard_state import QEMU_NBD_NBD_DEVICE


# https://qemu.readthedocs.io/en/latest/tools/qemu-nbd.html
class QemuImage(MetadataOnlyImage):
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

        # Ignore [/mnt/backup]/sbin/partclone.dd
        if filename.lower().endswith("partclone.dd"):
            return False

        # Don't match on Redo Rescue images, which have filenames such as "20210307_sda1_001.img"
        m = utility.REMatcher(filename)
        if m.match(r".*_\d\d\d\.img"):
            return False

        for key in supported_extensions.keys():
            for extension in supported_extensions[key]:
                if filename.lower().endswith(extension):
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
        self.absolute_path = absolute_qemu_img_path
        self.timeout_seconds = timeout_seconds
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

    def associate_nbd(self, nbd_device):
        is_success, error_message = self.deassociate_nbd(nbd_device)
        if not is_success:
            return False, error_message
        self.long_device_node = nbd_device
        # Does NOT mount images read-only to provide the ability to ntfsfix partitions as the standard Clonezilla
        # behavior is to eg, ntfsfix hibernated NTFS partitions during a restore.
        qemu_nbd_cmd_list = ["qemu-nbd", "--connect=" + nbd_device, self.absolute_path]
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
