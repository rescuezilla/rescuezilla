# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
#   Copyright (C) 2003-2021 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2019-2021 Rescuezilla.com <rescuezilla@gmail.com>
# ----------------------------------------------------------------------
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A Ps ARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------
import collections
import fileinput
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import threading
import traceback
from datetime import datetime
from time import sleep

import gi

from image_explorer_manager import ImageExplorerManager
from parser.chs_utilities import ChsUtilities
from parser.clonezilla_image import ClonezillaImage
from parser.fsarchiver_image import FsArchiverImage
from parser.metadata_only_image import MetadataOnlyImage
from parser.parted import Parted
from parser.sfdisk import Sfdisk
from wizard_state import IMAGE_EXPLORER_DIR, RESCUEZILLA_MOUNT_TMP_DIR

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, GLib

from logger import Logger
from parser.lvm import Lvm
from parser.partclone import Partclone
from parser.proc_partitions import ProcPartitions
from utility import ErrorMessageModalPopup, Utility, _


# Signals should automatically propagate to processes called with subprocess.run().

class RestoreManager:
    def __init__(self, builder):
        self.restore_in_progress_lock = threading.Lock()
        self.restore_in_progress = False
        self.builder = builder
        self.restore_progress = self.builder.get_object("restore_progress")
        self.clone_progress = self.builder.get_object("clone_progress")
        self.restore_progress_status = self.builder.get_object("restore_progress_status")
        self.clone_progress_status = self.builder.get_object("clone_progress_status")
        self.main_statusbar = self.builder.get_object("main_statusbar")
        self.logger = None
        # proc dictionary
        self.proc = collections.OrderedDict()
        self.requested_stop = False

    def is_restore_in_progress(self):
        with self.restore_in_progress_lock:
            return self.restore_in_progress

    def start_restore(self,
                      image,
                      restore_destination_drive,
                      restore_mapping_dict,
                      is_overwriting_partition_table,
                      is_rescue,
                      completed_callback,
                      on_separate_thread=True):
        self.restore_timestart = datetime.now()
        self.image = image
        if isinstance(self.image, MetadataOnlyImage):
            self.is_cloning = True
        else:
            self.is_cloning = False
        self.restore_destination_drive = restore_destination_drive
        self.restore_mapping_dict = restore_mapping_dict
        self.is_overwriting_partition_table = is_overwriting_partition_table
        self.is_rescue = is_rescue
        self.completed_callback = completed_callback
        self.logger = Logger("/tmp/rescuezilla.log." + datetime.now().strftime("%Y%m%dT%H%M%S") + ".txt")
        GLib.idle_add(self.update_progress_bar, 0)
        with self.restore_in_progress_lock:
            self.restore_in_progress = True
        if on_separate_thread:
            thread = threading.Thread(target=self.do_restore_wrapper)
            thread.daemon = True
            thread.start()
        else:
            return self.do_restore()

    # Intended to be called via event thread
    # Sending signals to process objects on its own thread. Relying on Python GIL.
    # TODO: Threading practices here need overhaul. Use threading.Lock() instead of GIL
    def cancel_restore(self):
        # Again, relying on GIL.
        self.requested_stop = True
        if len(self.proc) == 0:
            print("Nothing to cancel")
        else:
            print("Will send cancel signal to " + str(len(self.proc)) + " processes.")
            for key in self.proc.keys():
                process = self.proc[key]
                try:
                    print("Sending SIGTERM to " + str(process))
                    # Send SIGTERM
                    process.terminate()
                except:
                    print("Error killing process. (Maybe already dead?)")
        with self.restore_in_progress_lock:
            self.restore_in_progress = False
        if not self.is_cloning:
            self.completed_restore(False, _("Operation cancelled by user."))

    def display_status(self, msg1, msg2):
        GLib.idle_add(self.update_progress_status, msg1 + "\n" + msg2)
        if msg2 != "":
            status_bar_msg = msg1 + ": " + msg2
        else:
            status_bar_msg = msg1
        GLib.idle_add(self.update_main_statusbar, status_bar_msg)

    # Refresh partition table using partprobe, kpartx and `blockdev --rereadpt` based on Clonezilla's
    # inform_kernel_partition_table_changed function.
    #
    # Note: The partition table refresh is vital for successful restore, and has historically been big source of
    # error message displayed to the user. The partprobe/kpartx/blockdev utilities often have issues [1], so it appears
    # Clonezilla uses a combination of these to ensure reliable refresh.
    #
    # The function needs to work for GPT partition tables and legacy MBR partitions -- which initially will NOT have the
    # any Extended Boot Record information written, with the disks potentially busy.
    #
    # FIXME: The partition refresh approach needs to be re-evaluated for Rescuezilla (and arguably, Clonezilla).
    # FIXME: It may make sense to create patches to partprobe/kpartx/blockdev to ensure they always reliably work
    # FIXME: (including for MRR disks without EBR etc.) See [1] for how many other users experience similar issues with
    # FIXME: this.
    #
    # [1] https://serverfault.com/questions/36038/reread-partition-table-without-rebooting
    def update_kernel_partition_table(self, wait_for_partition):
        refresh_msg = _("Refreshing partition table")
        self.display_status(refresh_msg, _("Unmounting: {path}").format(path=self.restore_destination_drive))
        Utility.umount_warn_on_busy(self.restore_destination_drive)

        self.display_status(refresh_msg, _("Synchronizing disks..."))
        # Sync drives / flush buffers to avoid "Device or resource busy"
        process, flat_command_string, failed_message = Utility.run("Sync drives", ["sync"], use_c_locale=False,
                                                                   logger=self.logger)
        if process.returncode != 0:
            self.logger.write(failed_message)

        # Reread the partition table
        sleep(1.0)

        if shutil.which("partx") is not None:
            msg = _("Probing {device} with {app}").format(device=self.restore_destination_drive, app="partx")
            kpartx_rereadpt_cmd_list = ["partx", "--update", self.restore_destination_drive]
            self.display_status(refresh_msg, msg)
            process, flat_command_string, failed_message = Utility.run(msg
                , kpartx_rereadpt_cmd_list,
                use_c_locale=False, logger=self.logger)
            if process.returncode != 0:
                self.logger.write(failed_message)

        sleep(1.0)
        msg = _("Probing {device} with {app}").format(device=self.restore_destination_drive, app="hdparm")
        hdparm_rereadpt_cmd_list = ["hdparm", "-z", self.restore_destination_drive]
        self.display_status(refresh_msg, msg)
        process, flat_command_string, failed_message = Utility.run(
            msg,
            hdparm_rereadpt_cmd_list, use_c_locale=False, logger=self.logger)
        if process.returncode != 0:
            self.logger.write(failed_message)

        sleep(1.0)
        msg = _("Probing {device} with {app}").format(device=self.restore_destination_drive, app="partprobe")
        partprobe_rereadpt_cmd_list = ["partprobe", self.restore_destination_drive]
        self.display_status(refresh_msg, msg)
        process, flat_command_string, failed_message = Utility.run(
            msg,
            partprobe_rereadpt_cmd_list, use_c_locale=False, logger=self.logger)
        if process.returncode != 0:
            self.logger.write(failed_message)

        sleep(1.0)
        if shutil.which("kpartx") is not None:
            msg = _("Probing {device} with {app}").format(device=self.restore_destination_drive, app="kpartx")
            kpartx_rereadpt_cmd_list = ["kpartx", self.restore_destination_drive]
            self.display_status(refresh_msg, msg)
            process, flat_command_string, failed_message = Utility.run(
                msg, kpartx_rereadpt_cmd_list,
                use_c_locale=False, logger=self.logger)
            if process.returncode != 0:
                self.logger.write(failed_message)

        sleep(1.0)
        message = ""
        status_msg = _("Probing {device} with {app}").format(device=self.restore_destination_drive, app="blockdev")
        blockdev_rereadpt_cmd_list = ["blockdev", "--rereadpt", self.restore_destination_drive]
        self.display_status(refresh_msg, status_msg)
        process, flat_command_string, failed_message = Utility.run(
            status_msg,
            blockdev_rereadpt_cmd_list, use_c_locale=False, logger=self.logger)
        if process.returncode != 0:
            self.logger.write(failed_message)

        sleep(1.0)
        if wait_for_partition:
            short_restore_destination_device_node = re.sub('/dev/', '', self.restore_destination_drive)
            for i in range(1, 50):
                proc_partitions_string = Utility.read_file_into_string("/proc/partitions")
                if ProcPartitions.are_partitions_listed_in_proc_partitions(proc_partitions_string, short_restore_destination_device_node):
                    break
                sleep(0.2)

        # Only display error box if the blockdev command failed.
        if message != "":
            with self.summary_message_lock:
                self.summary_message += message + "\n"
            GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                          _("Failed to refresh the devices' partition table. This can happen if another process is accessing the partition table.") + "\n\n" + message)

        self.display_status("", "")
        return True,

    def clean_filesystem_header_in_partition(self, long_device_node):
        process, flat_command_string, failed_message = Utility.run("Running wipefs to erase filesystem headers",
                                                                   ["wipefs", "--all", long_device_node],
                                                                   use_c_locale=False, logger=self.logger)
        if process.returncode != 0:
            GLib.idle_add(self.completed_restore, False, failed_message)
            return False, failed_message

        process, flat_command_string, failed_message = Utility.run("Wipe first MB",
                                                                   ["dd", "if=/dev/zero", "of=" + long_device_node,
                                                                    "bs=1M", "count=1"], use_c_locale=False,
                                                                   logger=self.logger)
        if process.returncode != 0:
            GLib.idle_add(self.completed_restore, False, failed_message)
            return False, failed_message
        return True, ""

    def _shutdown_lvm(self):
        self.display_status(_("Scanning and unmounting any Logical Volume Manager (LVM) Logical Volumes..."), "")
        # Stop the Logical Volume Manager (LVM)
        failed_logical_volume_list, failed_volume_group_list = Lvm.shutdown_lvm2(self.builder, self.logger)
        for failed_volume_group in failed_volume_group_list:
            message = "Failed to shutdown Logical Volume Manager (LVM) Volume Group (VG): " + failed_volume_group[0] + "\n\n" + failed_volume_group[1]
            return False, message

        for failed_logical_volume in failed_logical_volume_list:
            message = "Failed to shutdown Logical Volume Manager (LVM) Logical Volume (LV): " + failed_logical_volume[0] + "\n\n" + failed_logical_volume[1]
            return False, message
        return True, ""

    # Copy file to temporary directory, as the Clonezilla codebase suggests:
    # "[..] mmap function maybe not available on remote disk (Ex. image is on samba disk).
    # We have to copy the config file to local disk. Thanks to Gerald HERMANT <ghermant _at_ astrel fr> for reporting this bugs."
    @staticmethod
    def create_temporary_copy(path, temp_filename):
        # Implementation copied from [1]
        # [1] https://stackoverflow.com/a/6587648/4745097
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, temp_filename)
        shutil.copy2(path, temp_path)
        return temp_path

    def do_restore_wrapper(self):
        try:
            self.do_restore()
        except Exception as exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            GLib.idle_add(self.completed_restore, False, _("Error restoring image: ") + tb)
            return

    def do_restore(self):
        self.requested_stop = False
        # Clear proc dictionary
        self.proc.clear()
        self.summary_message_lock = threading.Lock()
        self.summary_message = ""
        env = Utility.get_env_C_locale()

        with self.summary_message_lock:
            # Could state source image vs source drive depending on cloning/restoring an image of drive
            self.summary_message += _("Source image") + ": " + self.image.absolute_path + "\n"

        if self.is_rescue and not self.is_cloning:
            with self.summary_message_lock:
                self.summary_message += _("Rescue option is enabled.") + "\n"

        returncode, failed_message = ImageExplorerManager._do_unmount(IMAGE_EXPLORER_DIR, is_deassociate_qemu_nbd_device=False)
        if not returncode:
            with self.summary_message_lock:
                self.summary_message += failed_message + "\n"
            GLib.idle_add(self.completed_restore, False, failed_message)
            return False, failed_message

        returncode, failed_message = ImageExplorerManager._do_unmount(RESCUEZILLA_MOUNT_TMP_DIR, is_deassociate_qemu_nbd_device=False)
        if not returncode:
            with self.summary_message_lock:
                self.summary_message += failed_message + "\n"
            GLib.idle_add(self.completed_restore, False, failed_message)
            return False, failed_message

        is_successfully_shutdown, message = self._shutdown_lvm()
        if not is_successfully_shutdown:
            GLib.idle_add(self.completed_restore, False, message)
            return False, message

        # Determine the size of each partition, and the total size. This is used for the weighted progress bar
        total_size_estimate = 0
        if isinstance(self.image, FsArchiverImage):
            total_size_estimate = self.image.size_bytes
        else:
            for image_key in self.restore_mapping_dict.keys():
                if 'estimated_size_bytes' in self.image.image_format_dict_dict[image_key].keys():
                    # If the value took effort to compute it will be cached, so use the cached value.
                    estimated_size_bytes = self.image.image_format_dict_dict[image_key]['estimated_size_bytes']
                else:
                    # Otherwise, access the value
                    estimated_size_bytes = self.image._compute_partition_size_byte_estimate(image_key)
                self.restore_mapping_dict[image_key]['cumulative_bytes'] = total_size_estimate
                total_size_estimate += estimated_size_bytes
                # Save the value for easy access.
                self.restore_mapping_dict[image_key]['estimated_size_bytes'] = estimated_size_bytes

        # TODO: The following section handles images from each of the supported backup formats SEPARATELY.
        # TODO: This produces a MASSIVE amount of duplication, and makes it easier for lesser used code paths to
        # TODO: contain bugs. The logic from the original Clonezilla (ported to Python below) is by far the most robust
        # TODO: and well tested. Given the amount of special cases for eg, handling Redo Backup and Recovery images
        # TODO: it has not yet been feasible to combine the logic into a single function, but this is the long term
        # TODO: goal. It will allow future advancements like restoring to disks smaller than original to improve all
        # TODO: supported image formats.
        if not isinstance(self.image, FsArchiverImage):
            self.logger.write("Detected ClonezillaImage/FogProjectImage/RedoRescueImage/FoxcloneImage/QemuImage")
            image_dir = os.path.dirname(self.image.absolute_path)
            short_selected_image_drive_node = self.image.short_device_node_disk_list[0]

            # Clonezilla does this, but it should only effect legacy IDE drives and has no effect on newer drives.
            process, flat_command_string, failed_message = Utility.run("Forcing DMA transfer",
                                                                       ["hdparm", "-d1",
                                                                       self.restore_destination_drive],
                                                                       use_c_locale=False, logger=self.logger)
            if process.returncode != 0:
                # FIXME: Clonezilla always runs hdparm then ignores when hdparm errors out on non-IDE disks. For now Rescuezilla does the same.
                self.logger.write("Error writing hdparm: " + failed_message)

            if self.requested_stop:
                GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                return False, _("User requested operation to stop.")

            is_unmounted, message = Utility.umount_warn_on_busy(self.restore_destination_drive)
            if not is_unmounted:
                with self.summary_message_lock:
                    self.summary_message += message + "\n"
                GLib.idle_add(self.restore_destination_drive, False, message)

            if self.requested_stop:
                GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                return False, _("User requested operation to stop.")

            querying_geometry_msg = _("Querying hard drive geometry of {device}").format(device=self.restore_destination_drive)
            self.display_status(querying_geometry_msg, "")
            # Get the hard drive geometry, which while otherwise obsolete is important for NTFS filesystems.
            # See ChsUtilities for more information.
            destination_harddrive_geometry_dict, is_edd_geometry, message = ChsUtilities.query_drive_chs_geometry(long_device_node=self.restore_destination_drive,
                                                                                                 image_sfdisk_geometry_dict=self.image.sfdisk_chs_dict,
                                                                                                 logger=self.logger)
            if destination_harddrive_geometry_dict is None:
                # It's not fatal to failing to query geometry.
                print("Failed to query geometry dictionary: " + message)

            if self.is_overwriting_partition_table:
                process, flat_command_string, failed_message = Utility.run(
                    "Delete any existing MBR and GPT partition table on the destination disk: " + self.restore_destination_drive,
                    ["sgdisk", "--zap-all", self.restore_destination_drive], use_c_locale=False, logger=self.logger)
                if process.returncode != 0:
                    self.logger.write("sgdisk --zap-all failed (This is expected on a blank disk).")

                if not self.update_kernel_partition_table(wait_for_partition=False):
                    failed_message = _("Failed to refresh the devices' partition table. This can happen if another process is accessing the partition table.")
                    GLib.idle_add(self.completed_restore, False, failed_message)
                    return False, failed_message

                # Shutdown the Logical Volume Manager (LVM) again -- it seems the volume groups re-activate after partition table restored for some reason.
                # FIXME: Look into this.
                is_successfully_shutdown, message = self._shutdown_lvm()
                if not is_successfully_shutdown:
                    GLib.idle_add(self.completed_restore, False, message)
                    return False, message

                absolute_mbr_path = self.image.get_absolute_mbr_path()
                if absolute_mbr_path:
                    process, flat_command_string, failed_message = Utility.run("Restoring the first 446 bytes of MBR data (executable code area) for " + self.restore_destination_drive,
                                                                               ["dd", "if=" +
                                                                                absolute_mbr_path,
                                                                                "of=" + self.restore_destination_drive, "bs=446", "count=1"],
                                                                               use_c_locale=False, logger=self.logger)
                    if process.returncode != 0:
                        with self.summary_message_lock:
                            self.summary_message += failed_message
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                    if not self.update_kernel_partition_table(wait_for_partition=True):
                        failed_message = _("Failed to refresh the devices' partition table. This can happen if another process is accessing the partition table.")
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                    # Shutdown the Logical Volume Manager (LVM) again -- it seems the volume groups re-activate after partition table restored for some reason.
                    # FIXME: Look into this.
                    is_successfully_shutdown, message = self._shutdown_lvm()
                    if not is_successfully_shutdown:
                        GLib.idle_add(self.completed_restore, False, message)
                        return False, message
                else:
                    print("No MBR associated with " + short_selected_image_drive_node)

                if self.requested_stop:
                    GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                    return False, _("User requested operation to stop.")

                if self.image.normalized_sfdisk_dict['file_length'] == 0:
                    message = _("Could not restore sfdisk partition table as file has zero length: ") + \
                              str(self.image.normalized_sfdisk_dict['absolute_path'])
                    GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, message)
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
                else:
                    corrected_sfdisk_path = self.do_sfdisk_corrections(self.image.normalized_sfdisk_dict['absolute_path'])
                    cat_cmd_list = ["cat", corrected_sfdisk_path]

                    prefer_old_sfdisk_binary = False
                    if 'prefer_old_sfdisk_binary' in self.image.normalized_sfdisk_dict.keys():
                        prefer_old_sfdisk_binary = self.image.normalized_sfdisk_dict['prefer_old_sfdisk_binary']
                    sfdisk_cmd_list, warning_message = Sfdisk.get_sfdisk_cmd_list(self.restore_destination_drive,
                                                                                  prefer_old_sfdisk_binary)
                    if warning_message != "":
                        with self.summary_message_lock:
                            self.summary_message += message + "\n"
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, message)
                    if sfdisk_cmd_list is None:
                        failed_message = "sfdisk_cmd_list is None"
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                    Utility.print_cli_friendly("sfdisk ", [cat_cmd_list, sfdisk_cmd_list])
                    self.proc['cat_sfdisk'] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE, env=env,
                                                               encoding='utf-8')
                    self.proc['sfdisk'] = subprocess.Popen(sfdisk_cmd_list, stdin=self.proc['cat_sfdisk'].stdout,
                                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, encoding='utf-8')
                    self.proc['cat_sfdisk'].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
                    output, err = self.proc['sfdisk'].communicate()
                    rc = self.proc['sfdisk'].returncode
                    self.logger.write("sfdisk Exit output " + str(rc) + ": " + str(output))
                    if self.proc['sfdisk'].returncode != 0:
                        failed_message = "Error restoring sfdisk: " + str(output)
                        self.logger.write(failed_message)
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message
                    else:
                        with self.summary_message_lock:
                            self.summary_message += _("Successfully restored partition table.") + "\n"
                        os.remove(corrected_sfdisk_path)

                    # Sync drives / flush buffers to avoid "Device or resource busy"
                    process, flat_command_string, failed_message = Utility.run("Sync drives", ["sync"],
                                                                               use_c_locale=False,
                                                                               logger=self.logger)
                    if process.returncode != 0:
                        with self.summary_message_lock:
                            self.summary_message += failed_message
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                if self.requested_stop:
                    GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                    return False, _("User requested operation to stop.")

                # Shutdown the Logical Volume Manager (LVM) again -- it seems the volume groups re-activate after partition table restored for some reason.
                # FIXME: Look into this.
                is_successfully_shutdown, message = self._shutdown_lvm()
                if not is_successfully_shutdown:
                    GLib.idle_add(self.completed_restore, False, message)
                    return False, message

                if not self.update_kernel_partition_table(wait_for_partition=True):
                    failed_message = _("Failed to refresh the devices' partition table. This can happen if another process is accessing the partition table.")
                    GLib.idle_add(self.completed_restore, False, failed_message)
                    return False, failed_message

                if self.requested_stop:
                    GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                    return False, _("User requested operation to stop.")

                # Overwrite the post-MBR gap (if it exists). This file is typically 1 megabyte but may be a maximum
                # of 1024 megabytes. For the post-MBR gap to be overwritten the user has requested the destination
                # disk partition table to be overwritten. Rescuezilla's user interface makes the implications of this
                # clear. Note: this operation means writing to disk the entirety of the (even 1024MB) post-MBR gap
                # backup.
                #
                # The nature of accepting a partition table overwrite means there's no risk of overwriting data that
                # the user didn't intend on overwriting: all partitions are coming from a backup image so eg,
                # calculating offsets to the first partition and comparing it to the post-MBR gap file size prevent
                # accidentally overwriting it is NOT required here. The only gotcha is GPT disks, where overwriting the
                # post-MBR gap can cause an inconsistent state, at least on FOG Project images.
                if Sfdisk.has_dos_partition_table(self.image.normalized_sfdisk_dict):
                    print("Found DOS partition table.")
                    restore_post_mbr_gap_cmd_list = []
                    post_mbr_gap_restore_msg = ""
                    if 'absolute_path' in self.image.post_mbr_gap_dict.keys():
                        post_mbr_gap_restore_msg = "Restoring post-MBR gap using " + self.image.post_mbr_gap_dict['absolute_path']
                        # If we have a post-MBR gap file (like Clonezilla), just use it.
                        restore_post_mbr_gap_cmd_list = ["dd", "if=" + self.image.post_mbr_gap_dict['absolute_path'],
                                                         "of=" + self.restore_destination_drive,
                                                         # Write to 1 block into the destination device
                                                         "seek=1",
                                                         "bs=512"]
                    else:
                        mbr_size = int(os.stat(absolute_mbr_path).st_size)
                        if mbr_size > 512:
                            post_mbr_gap_restore_msg = "Restoring post-MBR gap by carefully using MBR file (" + absolute_mbr_path + "), as it's larger than 512 bytes: " + str(mbr_size)
                            # For image formats that combine the MBR and post-MBR gap together, carefully use dd write
                            # the post-MBR gap into the correct place
                            restore_post_mbr_gap_cmd_list = ["dd", "if=" + absolute_mbr_path,
                                                             "of=" + self.restore_destination_drive,
                                                             # Read from 1 block into the source file
                                                             "skip=1",
                                                             # Write to 1 block into the destination device
                                                             "seek=1",
                                                             "bs=512"]
                        else:
                            print("No post-MBR gap file found.")

                    if len(restore_post_mbr_gap_cmd_list) > 0:
                        process, flat_command_string, failed_message = Utility.run(post_mbr_gap_restore_msg,
                                                                                   restore_post_mbr_gap_cmd_list,
                                                                                   use_c_locale=False, logger=self.logger)
                        if process.returncode != 0:
                            with self.summary_message_lock:
                                self.summary_message += failed_message
                            GLib.idle_add(self.completed_restore, False, failed_message)
                            return False, failed_message

                        if self.requested_stop:
                            GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                            return False, _("User requested operation to stop.")

                        if not self.update_kernel_partition_table(wait_for_partition=True):
                            failed_message = _(
                                              "Failed to refresh kernel partition table. This can happen if another process is accessing the partition table.")
                            GLib.idle_add(self.completed_restore, False, failed_message)
                            return False, failed_message

                        # Shutdown the Logical Volume Manager (LVM) again -- it seems the volume groups re-activate after partition table restored for some reason.
                        # FIXME: Look into this.
                        is_successfully_shutdown, message = self._shutdown_lvm()
                        if not is_successfully_shutdown:
                            GLib.idle_add(self.completed_restore, False, message)
                            return False, message

                        if self.requested_stop:
                            GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                            return False, _("User requested operation to stop.")

                # The Extended Boot Record (EBR) information is already captured in the .sfdisk file, which provides
                # greater flexibility around destination hard drive sizes. The '-ebr' image files in the Clonezilla
                # backup has fixed size offsets so don't handle different destination hard drive sizes well, causing
                # re-reading the partition table to fail. Because of this, we ignore the '-ebr' files.
                #
                # TODO: If this reasoning stands up to scrutiny, the code below can be deleted.
                # There is a maximum of 1 EBR per drive (but there can be many drives)
                relevant_ebr_list = [image_number for image_number in self.image.ebr_dict.keys() if
                                     image_number.startswith(short_selected_image_drive_node)]
                if len(relevant_ebr_list) > 1:
                    failed_message = "Found multiple Extended Boot Records for " + short_selected_image_drive_node + " " + str(
                                      relevant_ebr_list)
                    GLib.idle_add(self.completed_restore, False, failed_message)
                    return False, failed_message
                elif len(relevant_ebr_list) == 1:
                    # Restore EBR.
                    base_image_device, image_partition_number = Utility.split_device_string(
                        self.image.ebr_dict[short_selected_image_drive_node]['short_device_node'])
                    dest_ebr_short_device_node = Utility.join_device_string(self.restore_destination_drive,
                                                                            image_partition_number)
                    process, flat_command_string, failed_message = Utility.run("Restoring the first 446 bytes of EBR (Extended boot Record) data for extended partition " + dest_ebr_short_device_node + " by",
                                                                               ["dd", "if=" + self.image.ebr_dict[short_selected_image_drive_node]['absolute_path'], "of=" + dest_ebr_short_device_node, "bs=446", "count=1"],
                                                                               use_c_locale=False, logger=self.logger)

                    if process.returncode != 0:
                        with self.summary_message_lock:
                            self.summary_message += failed_message
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                    if self.requested_stop:
                        GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                        return False, _("User requested operation to stop.")

                    if not self.update_kernel_partition_table(wait_for_partition=True):
                        failed_message = _(
                                          "Failed to refresh kernel partition table. This can happen if another process is accessing the partition table.")
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                    # Shutdown the Logical Volume Manager (LVM) again -- it seems the volume groups re-activate after partition table restored for some reason.
                    # FIXME: Look into this.
                    is_successfully_shutdown, message = self._shutdown_lvm()
                    if not is_successfully_shutdown:
                        GLib.idle_add(self.completed_restore, False, message)
                        return False, message

                    if self.requested_stop:
                        GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                        return False, _("User requested operation to stop.")

                # Shutdown the Logical Volume Manager (LVM) again -- it seems the volume groups re-activate after partition table restored for some reason.
                # FIXME: Look into this.
                is_successfully_shutdown, message = self._shutdown_lvm()
                if not is_successfully_shutdown:
                    GLib.idle_add(self.completed_restore, False, message)
                    return False, message

                # Given the partition table is being overwritten, restore LVM Physical Volume and Volume Groups
                # Restore Logical Volume Manager (LVM)'s Physical Volume (PV) and Volume Group (VG) data
                # This code is based on Clonezilla's restore_logv(), which says:
                #
                # "Part of these codes are from http://www.trickytools.com/php/clonesys.php"
                # "Thanks to Jerome Delamarche (jd@inodes-fr.com)"
                for volume_group_key in self.image.lvm_vg_dev_dict.keys():
                    # Handle multiple disk case
                    if not self.image.is_volume_group_in_pv(volume_group_key):
                        print("Volume group key" + volume_group_key + " not in current device's physical volume list")
                        continue
                    image_pv_base_device_node, image_pv_partition_number = Utility.split_device_string(
                        self.image.lvm_vg_dev_dict[volume_group_key]['device_node'])
                    # Generate a device node to write the physical volume to.
                    destination_pv_long_device_node = Utility.join_device_string(self.restore_destination_drive,
                                                                                 image_pv_partition_number)
                    uuid = self.image.lvm_vg_dev_dict[volume_group_key]['uuid']
                    lvm_vg_conf_filepath = os.path.join(image_dir, "lvm_" + volume_group_key + ".conf")
                    if volume_group_key == "/NOT_FOUND" or not os.path.isfile(lvm_vg_conf_filepath):
                        # Prevent pvcreate returning an error like "Device /dev/[...] excluded by a filter."
                        is_success, failed_message = self.clean_filesystem_header_in_partition(destination_pv_long_device_node)
                        if not is_success:
                            # Error callback handled in the function
                            return False, failed_message
                        pvcreate_cmd_list = ["pvcreate", "-ff", "--yes", "--uuid=" + uuid, "--zero", "y",
                                             destination_pv_long_device_node]
                        process, flat_command_string, failed_message = Utility.run(
                            "Logical Volume Manager (LVM) Physical Volume (PV) Creation",
                            pvcreate_cmd_list, use_c_locale=False, logger=self.logger)
                        if process.returncode != 0:
                            with self.summary_message_lock:
                                self.summary_message += failed_message
                            GLib.idle_add(self.completed_restore, False, failed_message)
                            return False, failed_message
                    else:
                        # Clonezilla codebase suggests remote disks may not be able to mmap the file, so make a temp copy.
                        lvm_vg_conf_filepath_tmp_copy = RestoreManager.create_temporary_copy(lvm_vg_conf_filepath,
                                                                                             "temp.lvm_" + volume_group_key + ".conf")
                        pvcreate_cmd_list = ["pvcreate", "-ff", "--yes", "--uuid", uuid, "--zero", "y", "--restorefile",
                                             lvm_vg_conf_filepath_tmp_copy, destination_pv_long_device_node]
                        process, flat_command_string, failed_message = Utility.run(
                            "Logical Volume Manager (LVM) Physical Volume (PV) Creation",
                            pvcreate_cmd_list, use_c_locale=False, logger=self.logger)
                        if process.returncode != 0:
                            with self.summary_message_lock:
                                self.summary_message += failed_message
                            GLib.idle_add(self.completed_restore, False, failed_message)
                            return False, failed_message
                        else:
                            # Delete the temp copy
                            os.remove(lvm_vg_conf_filepath_tmp_copy)

                for volume_group_key in self.image.lvm_vg_dev_dict.keys():
                    # Check if vg already exists. From Clonezilla:
                    # //NOTE// VG might exist in more than one PV. If so, we only have to create it once.
                    # E.g.,
                    # centos7 /dev/sda2 UUID
                    # centos7 /dev/sda3 UUID
                    # Ref: https://sourceforge.net/p/clonezilla/discussion/Help/thread/13f8ed6643/?limit=25#4ae4
                    process, flat_command_string, failed_message = Utility.run( "Checking if VG already exists",
                        ["vgs", volume_group_key], use_c_locale=False, logger=self.logger)
                    if process.returncode == 0:
                        # VG exists
                        continue

                    # Handle multiple disk case
                    if not self.image.is_volume_group_in_pv(volume_group_key):
                        print("Volume group key" + volume_group_key + " not in current device's physical volume list")
                        continue
                    lvm_vg_conf_filepath = os.path.join(image_dir, "lvm_" + volume_group_key + ".conf")
                    # Clonezilla codebase suggests remote disks may not be able to mmap the file, so make a temp copy.
                    lvm_vg_conf_filepath_tmp_copy = RestoreManager.create_temporary_copy(lvm_vg_conf_filepath,
                                                                                         "temp.lvm_" + volume_group_key + ".conf")
                    # "Add --force to force metadata restore even with thin pool LVs"
                    vgcreate_cmd_list = ["vgcfgrestore", "--force", "--file", lvm_vg_conf_filepath_tmp_copy, volume_group_key]
                    process, flat_command_string, failed_message = Utility.run(
                        "Restore Logical Volume Manager (LVM) Volume Group (VG) configuration", vgcreate_cmd_list,
                        use_c_locale=False, logger=self.logger)

                    if process.returncode != 0:
                        with self.summary_message_lock:
                            self.summary_message += failed_message
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message
                    else:
                        # Delete the temp copy
                        os.remove(lvm_vg_conf_filepath_tmp_copy)

            # Currently Rescuezilla's native formats (Clonezilla and MetadataOnlyImage) are the only image format that
            # handles LVMs as anything other than a raw dd device so after restoring the configuration, start the LVM
            # for these formats only.
            if isinstance(self.image, ClonezillaImage) or isinstance(self.image, MetadataOnlyImage):
                self.display_status(_("Starting Logical Volume Manager (LVM) Logical Volumes..."), "")
                # Start the Logical Volume Manager (LVM). Caller raises Exception on failure
                Lvm.start_lvm2(self.logger)

            # Sanity check block devices
            target_block_devices_exist = False
            partition_table_message = ""

            if target_block_devices_exist:
                self.logger.write(partition_table_message)
                with self.summary_message_lock:
                    self.summary_message += partition_table_message + "\n"
                GLib.idle_add(self.restore_destination_drive, False, message)

            image_number = 0
            for image_key in self.restore_mapping_dict.keys():
                image_number += 1
                total_progress_float = Utility.calculate_progress_ratio(current_partition_completed_percentage=0,
                                 current_partition_bytes=self.restore_mapping_dict[image_key]['estimated_size_bytes'],
                                 cumulative_bytes=self.restore_mapping_dict[image_key]['cumulative_bytes'],
                                 total_bytes=total_size_estimate,
                                 image_number=image_number,
                                 num_partitions=len(self.restore_mapping_dict.keys()))
                GLib.idle_add(self.update_progress_bar, total_progress_float)

                dest_part = self.restore_mapping_dict[image_key]
                if self.image.image_format_dict_dict[image_key]['is_lvm_logical_volume']:
                    # Erase the filesytem header when it exists
                    is_success, failed_message = self.clean_filesystem_header_in_partition(dest_part['dest_key'])
                    if not is_success:
                        # Error callback handled in the function
                        return False, failed_message

                is_unmounted, message = Utility.umount_warn_on_busy(dest_part['dest_key'])
                if not is_unmounted:
                    self.logger.write(message)
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
                    GLib.idle_add(self.restore_destination_drive, False, message)

                if self.requested_stop:
                    GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                    return False, _("User requested operation to stop.")

                filesystem_restore_message = _(
                    "Restoring {description} to {destination_partition} ({destination_description})").format(
                    description=dest_part['description'], destination_partition=dest_part['dest_key'],
                    destination_description=dest_part['dest_description'])
                self.logger.write(filesystem_restore_message)
                GLib.idle_add(self.display_status, filesystem_restore_message, "")
                # Restore filesystem. Implements Clonezillas "unicast_restore_by_partclone", "unicast_restore_by_partimage", "unicast_restore_by_ntfsclone"
                if 'type' in self.image.image_format_dict_dict[image_key].keys():
                    image_type = self.image.image_format_dict_dict[image_key]['type']
                    if image_type == 'swap':
                        self.logger.write("Considering " + image_key + "\n")
                        swap_cmd_list = ["mkswap"]
                        if self.image.image_format_dict_dict[image_key]['label'] != "":
                            swap_cmd_list.append("--label=" + self.image.image_format_dict_dict[image_key]['label'])
                        if self.image.image_format_dict_dict[image_key]['uuid'] != "":
                            swap_cmd_list.append("--uuid=" + self.image.image_format_dict_dict[image_key]['uuid'])
                        swap_cmd_list.append(dest_part['dest_key'])
                        # Restore swap. Clonezilla reads from sfdisk for MBR and from parted for GPT.
                        process, flat_command_string, failed_message = Utility.run("Recreate swap partition",
                                                                                   swap_cmd_list,
                                                                                   use_c_locale=False,
                                                                                   logger=self.logger)
                        if process.returncode != 0:
                            with self.summary_message_lock:
                                self.summary_message += failed_message
                            GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                          failed_message)
                            GLib.idle_add(self.completed_restore, False, failed_message)
                            return False, failed_message
                        else:
                            with self.summary_message_lock:
                                self.summary_message += _(
                                    "Successfully restored image partition {image} to {destination_partition}").format(
                                    image=image_key, destination_partition=dest_part['dest_key']) + ".\n"
                        continue
                    if image_type == 'missing':
                        image_base_device_node, image_partition_number = Utility.split_device_string(image_key)
                        # FIXME: Ensure the assertion that the key being used is valid for the dictionary is true.
                        flat_description = "Partition " + str(
                            image_partition_number) + ": " + self.image.flatten_partition_string(image_key)
                        partition_summary = "<b>" + _("Unable to restore partition {destination_partition} because there is no saved image associated with: {description}.").format(
                            destination_partition=dest_part['dest_key'], description=flat_description) + "</b>\n\n" + _(
                            "This may occur if Clonezilla was originally unable to backup this partition.") + "\n"
                        with self.summary_message_lock:
                            self.summary_message += partition_summary
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                      partition_summary)
                        continue
                    if self.is_cloning:
                        # FIXME: Remove this ugly hacky approach of making cat and decompression a no-op
                        cat_cmd_list = ["true"]
                        decompression_cmd_list = ["true"]
                    else:
                        cat_cmd_list = ["cat"] + self.image.image_format_dict_dict[image_key]['absolute_filename_glob_list']
                        decompression_cmd_list = Utility.get_decompression_command_list(self.image.image_format_dict_dict[image_key]['compression'])

                    restore_binary = self.image.image_format_dict_dict[image_key]['binary']
                    use_old_partclone = False
                    if 'use_old_partclone' in self.image.image_format_dict_dict[image_key].keys():
                        use_old_partclone = self.image.image_format_dict_dict[image_key]['use_old_partclone']
                        if use_old_partclone:
                            memory_bus_width = Utility.get_memory_bus_width()
                            old_partclone_ver = "v0.2.43." + memory_bus_width
                            restore_binary = "partclone.restore" + "." + old_partclone_ver
                            if shutil.which(restore_binary) is None:
                                message = "Could not find old partclone binary to maximize backwards compatibility: " + restore_binary + ". Will fallback to modern partclone version." + "\n"
                                with self.summary_message_lock:
                                    self.summary_message += message + "\n"
                                restore_binary = self.image.image_format_dict_dict[image_key]['binary']
                                use_old_partclone = False

                    if shutil.which(restore_binary) is None:
                        message = "Cannot restore " + dest_part[
                            'dest_key'] + ": " + restore_binary + ": Not found\n\nPartition " + image_key + " cannot be restored unless this utility is installed."
                        with self.summary_message_lock:
                            self.summary_message += message + "\n"
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, message)
                        continue

                    valid_filename_dest_key = re.sub('/', '-', dest_part['dest_key'])
                    log_filepath = "/tmp/rescuezilla.logfile." + valid_filename_dest_key + "." + restore_binary + ".txt"
                    if 'TERM' in env.keys():
                        env.pop('TERM')

                    if 'dd' == image_type or restore_binary == "partclone.dd":
                        # TODO: $PARTCLONE_RESTORE_OPT
                        # 16MB partclone dd blocksize (from Clonezilla)
                        partclone_dd_blocksize = "16777216"
                        if self.is_cloning:
                            restore_command_list = [restore_binary] + Utility.get_partclone_rescue_options(self.is_rescue) + ["--buffer_size", partclone_dd_blocksize, "--logfile",
                                                log_filepath, "--source", image_key, "--overwrite",
                                                dest_part['dest_key']]
                        else:
                            restore_command_list = [restore_binary] + Utility.get_partclone_rescue_options(self.is_rescue) + ["--buffer_size", partclone_dd_blocksize, "--logfile",
                                                log_filepath, "--source", "-", "--overwrite",
                                                dest_part['dest_key']]
                    elif 'partclone' == image_type:
                        if use_old_partclone:
                            restore_command_list = [restore_binary] + Utility.get_partclone_rescue_options(self.is_rescue) + ["--logfile", log_filepath,
                                                    "--overwrite", dest_part['dest_key']]
                        else:
                            if self.is_cloning:
                                # Partclone images require --dev-to-dev when cloning device-to-device. Except dd images,
                                # which don't need it. (Note: Clonezilla's ptcl-img dd image is different to its dd-img)
                                restore_command_list = [restore_binary] + Utility.get_partclone_rescue_options(self.is_rescue) + ["--dev-to-dev", "--logfile", log_filepath, "--source",
                                                    image_key, "--overwrite", dest_part['dest_key']]
                            else:
                                # TODO: $PARTCLONE_RESTORE_OPT
                                restore_command_list = [restore_binary] + Utility.get_partclone_rescue_options(self.is_rescue) + ["--logfile", log_filepath, "--source",
                                                        "-", "--restore", "--overwrite", dest_part['dest_key']]
                    elif 'partimage' == image_type:
                        # TODO: partimage will put header in 2nd and later volumes, so we have to uncompress it, then strip it before pipe them to partimage
                        restore_command_list = [restore_binary, "--batch", "--finish=3", "--overwrite", "--nodesc",
                                                "restore", dest_part['dest_key'], "stdin"]
                        restore_stdin_proc_key = 'cat_' + image_key
                        env['TERM'] = "xterm"
                    elif 'ntfsclone' == image_type:
                        # TODO: Evaluate $ntfsclone_restore_extra_opt_def
                        restore_command_list = [restore_binary, "--restore-image", "--overwrite", dest_part['dest_key'],
                                                "-"]
                    else:
                        message = "Unhandled type" + image_type + " from " + image_key
                        self.logger.write(message)
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, message)
                        with self.summary_message_lock:
                            self.summary_message += message + "\n"
                        continue

                    if "unknown" != image_type:
                        if self.is_cloning:
                            flat_command_string = Utility.print_cli_friendly(image_type + " command ",
                                                                         [restore_command_list])
                        else:
                            flat_command_string = Utility.print_cli_friendly(image_type + " command ",
                                                                         [cat_cmd_list, decompression_cmd_list,
                                                                          restore_command_list])
                        self.proc['cat_' + image_key] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE,
                                                                         env=env,
                                                                         encoding='utf-8')
                        restore_stdin_proc_key = 'decompression_' + image_key
                        self.proc[restore_stdin_proc_key] = subprocess.Popen(decompression_cmd_list,
                                                                                   stdin=self.proc[
                                                                                       'cat_' + image_key].stdout,
                                                                                   stdout=subprocess.PIPE, env=env,
                                                                                   encoding='utf-8')
                    """else:
                        flat_command_string = Utility.print_cli_friendly(image_type + " command ",
                                                   [cat_cmd_list, restore_command_list])
                        self.proc['cat_' + image_key] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE,
                                                                         env=env,
                                                                         encoding='utf-8')
                        restore_stdin_proc_key = 'cat_' + image_key"""
                    if self.is_cloning:
                        flat_command_string = Utility.print_cli_friendly(image_type + " command ",
                                                                         [restore_command_list])
                        self.proc[image_type + '_restore_' + image_key] = subprocess.Popen(restore_command_list,
                                                                                       stdout=subprocess.PIPE,
                                                                                       stderr=subprocess.PIPE, env=env,
                                                                                       encoding='utf-8')
                    else:
                        self.proc[image_type + '_restore_' + image_key] = subprocess.Popen(restore_command_list,
                                                                                       stdin=self.proc[
                                                                                           restore_stdin_proc_key].stdout,
                                                                                       stdout=subprocess.PIPE,
                                                                                       stderr=subprocess.PIPE, env=env,
                                                                                       encoding='utf-8')

                    # Process partclone output. Partclone outputs an update every 3 seconds, so processing the data
                    # on the current thread, for simplicity.
                    # Poll process.stdout to show stdout live
                    proc_stdout = ""
                    proc_stderr = ""
                    while True:
                        if self.requested_stop:
                            GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                            return False, _("User requested operation to stop.")

                        output = self.proc[image_type + '_restore_' + image_key].stderr.readline()
                        proc_stderr += output
                        if self.proc[image_type + '_restore_' + image_key].poll() is not None:
                            break
                        if output and ("partclone" == image_type or "dd" == image_type):
                            temp_dict = Partclone.parse_partclone_output(output)
                            if 'completed' in temp_dict.keys():
                                total_progress_float = Utility.calculate_progress_ratio(
                                    current_partition_completed_percentage=temp_dict['completed'] / 100.0,
                                    current_partition_bytes=self.restore_mapping_dict[image_key][
                                        'estimated_size_bytes'],
                                    cumulative_bytes=self.restore_mapping_dict[image_key]['cumulative_bytes'],
                                    total_bytes=total_size_estimate,
                                    image_number=image_number,
                                    num_partitions=len(self.restore_mapping_dict.keys()))
                                GLib.idle_add(self.update_progress_bar, total_progress_float)
                            if 'remaining' in temp_dict.keys():
                                GLib.idle_add(self.update_progress_status,
                                              filesystem_restore_message + "\n\n" + output)
                        elif "partimage" == image_type:
                            self.display_status("partimage: " + filesystem_restore_message, "")
                        elif "ntfsclone" == image_type:
                            self.display_status("ntfsclone: " + filesystem_restore_message, "")

                        rc = self.proc[image_type + '_restore_' + image_key].poll()

                    self.proc['cat_' + image_key].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
                    if "unknown" != image_type:
                        self.proc[
                            'decompression_' + image_key].stdout.close()  # Allow p2 to receive a SIGPIPE if p3 exits.
                    stdout, stderr = self.proc[image_type + '_restore_' + image_key].communicate()
                    rc = self.proc[image_type + '_restore_' + image_key].returncode
                    proc_stdout += stdout
                    proc_stderr += stderr
                    self.logger.write("Exit output " + str(rc) + ": " + str(proc_stdout) + "stderr " + str(proc_stderr))
                    if self.proc[image_type + '_restore_' + image_key].returncode != 0:
                        partition_summary = _(
                            "Error restoring partition {image_key} to {destination_partition}.").format(
                            image_key=image_key, destination_partition=dest_part['dest_key']) + "\n"
                        extra_info = "\nThe command used internally was:\n\n" + flat_command_string + "\n\n" + "The output of the command was: " + str(
                            proc_stdout) + "\n\n" + str(proc_stderr)
                        decompression_stderr = self.proc['decompression_' + image_key].stderr
                        if decompression_stderr is not None and decompression_stderr != "":
                            extra_info += "\n\n" + decompression_cmd_list[0] + " stderr: " + decompression_stderr
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                      partition_summary + extra_info)
                        with self.summary_message_lock:
                            self.summary_message += partition_summary
                        continue
                    else:
                        with self.summary_message_lock:
                            self.summary_message += _(
                                "Successfully restored image partition {image} to {destination_partition}").format(
                                image=image_key, destination_partition=dest_part['dest_key']) + ".\n"
                else:
                    message = _("Unable to find restore type for partition: {image_key}").format(image_key=image_key)
                    self.logger.write(message + " in " + str(self.image.image_format_dict_dict))
                    GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, "<b>" + message + "</b>")
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
                    continue

                filesystem=""
                if 'filesystem' in self.image.image_format_dict_dict[image_key].keys() \
                        and not self.image.image_format_dict_dict[image_key]['is_lvm_logical_volume']:
                    filesystem = self.image.image_format_dict_dict[image_key]['filesystem']
                    growing_filesystem_message = _(
                        "Growing filesystem {partition} ({filesystem}). This may take a while...").format(
                        partition=dest_part['dest_key'], filesystem=filesystem)
                    self.logger.write(growing_filesystem_message)
                    GLib.idle_add(self.display_status, growing_filesystem_message, "")
                    is_success, failed_message = Utility.grow_filesystems(filesystem, dest_part['dest_key'], self.logger)
                    if not is_success:
                        message = _("Resizing partition {partition} ({filesystem}) failed: {msg}").format(partition=dest_part['dest_key'], filesystem=filesystem, msg=failed_message)
                        self.logger.write(message + "\n")
                        with self.summary_message_lock:
                            self.summary_message += message + "\n"
                        continue
                GLib.idle_add(self.display_status, "", "")

                # TODO: Implement Clonezilla's "Do files checksum check. This must be before any further commands (like grub reinstalling) are done."
                # Note: This is only checked if "$chk_chksum_for_files_in_dev" / -cmf is enabled (which is non-default),
                # and the check is not actually required before GRUB re-installation except for obviously invalidating
                # checksums)

                if "ntfs" == filesystem:
                    GLib.idle_add(self.display_status,
                                  _("Running {app} on {device}").format(app="ntfsfix", device=dest_part['dest_key']), "")
                    is_success, failed_message = Utility.run_ntfsfix(dest_part['dest_key'])
                    if not is_success:
                        self.logger.write(failed_message + "\n")
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)
                        with self.summary_message_lock:
                            self.summary_message += failed_message + "\n"

                    # Get the NTFS partition's start sector from the Parted dictionary
                    base_device, partition_number = Utility.split_device_string(dest_part['dest_key'])
                    ntfs_partition_start_sector = None
                    try:
                        ntfs_partition_start_sector = self.image.parted_dict['partitions'][partition_number]['start']
                    except:
                        print("Couldn't get start sector from parted dict")
                        tb = traceback.format_exc()
                        traceback.print_exc()
                    # Adjust the NTFS filesystem CHS (cylinder-head-sector) information.
                    # Note: Clonezilla's run_ntfsreloc_part function from sbin/ocs-functions file only adjusts
                    # partitions containing the boot flag, but adjusting all NTFS filesystem seems to make more sense.
                    is_success, message = ChsUtilities.adjust_ntfs_filesystem_chs_geometry_information(
                        ntfs_partition_long_device_node=dest_part['dest_key'],
                        ntfs_partition_start_sector=ntfs_partition_start_sector,
                        destination_disk_geometry_dict=destination_harddrive_geometry_dict,
                        is_edd_geometry=is_edd_geometry,
                        logger=self.logger)

                    self.logger.write(message + "\n")
                    if not is_success:
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, message)
                        with self.summary_message_lock:
                            self.summary_message += _("Failed to adjust NTFS filesystem geometry of {ntfs_device}").format(ntfs_device=dest_part['dest_key']) + "\n"
                    else:
                        with self.summary_message_lock:
                            self.summary_message += message + "\n"

            # After restoring all partitions we can start LVM for all other formats, so that post-processing
            # steps have a chance of operating on logical volumes.
            if not (isinstance(self.image, ClonezillaImage) or isinstance(self.image, MetadataOnlyImage)):
                self.display_status(_("Starting Logical Volume Manager (LVM) Logical Volumes..."), "")
                # Start the Logical Volume Manager (LVM). Caller raises Exception on failure
                Lvm.start_lvm2(self.logger)

            # Clonezilla bash scripts take partition list without leading /dev/, and as a single argument string.
            restore_destination_drive_short_dev_node = re.sub('/dev/', '', self.restore_destination_drive)
            dest_partition_short_dev_node_string = ""
            for image_key in self.restore_mapping_dict.keys():
                dest_partition_short_dev_node_string += re.sub('/dev/', '', self.restore_mapping_dict[image_key]['dest_key']) + " "

            if shutil.which("ocs-tux-postprocess") is not None:
                GLib.idle_add(self.display_status, _("Removing udev MAC address records (if any)"), "")
                # TODO: Port Clonezilla's ocs-tux-postprocess bash script to Python instead of relying on Clonezilla's script
                process, flat_command_string, failed_message = Utility.run(
                   "Remove the udev MAC address records on the restored GNU/Linux (if any)",
                    ["ocs-tux-postprocess", dest_partition_short_dev_node_string], use_c_locale=False, logger=self.logger)
                if process.returncode == 0:
                    message = "Successfully removed any udev MAC address records"
                    self.logger.write(message + "\n")
                    # Not displaying this to users because it wil lbe confusing for end-users.
            else:
                message = "Not removing udev MAC address records: Unable to find ocs-tux-postprocess. Is Clonezilla installed?"
                self.logger.write(message + "\n")
                with self.summary_message_lock:
                    self.summary_message += message + "\n"

            if shutil.which("ocs-update-syslinux") is not None:
                GLib.idle_add(self.display_status, _("Re-installing syslinux (if any)"), "")
                # TODO: Port Clonezilla's ocs-update-syslinux bash script to Python instead of relying on Clonezilla's script
                process, flat_command_string, failed_message = Utility.run(
                   "Re-install syslinux (if any)",
                    ["ocs-update-syslinux", "--batch", dest_partition_short_dev_node_string], use_c_locale=False, logger=self.logger)
                if process.returncode == 0:
                    message = _("Successfully re-installed syslinux bootloader")
                    self.logger.write(message + "\n")
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
            else:
                message = "Not re-installing syslinux: Unable to find ocs-update-syslinux. Is Clonezilla installed?"
                self.logger.write(message + "\n")
                with self.summary_message_lock:
                    self.summary_message += message + "\n"

            if shutil.which("ocs-install-grub") is not None:
                GLib.idle_add(self.display_status, _("Re-installing GRUB bootloader (if any)"), "")
                # TODO: Port Clonezilla's ocs-install-grub bash script to Python instead of relying on Clonezilla's script
                process, flat_command_string, failed_message = Utility.run(
                   "Re-installing GRUB bootloader (if any)",
                    ["ocs-install-grub", "--selected-parts", dest_partition_short_dev_node_string,
                     "--selected-hd", restore_destination_drive_short_dev_node, "auto"], use_c_locale=False, logger=self.logger)
                # Returns 0 on GRUB re-install success, but returns -1 even if GRUB not found
                if process.returncode == 0:
                    message = _("Successfully re-installed GRUB bootloader")
                    for line in process.stderr:
                        if "Installing for" in line:
                            message += ": " + line.sub("Installing for ")
                    self.logger.write(message + "\n")
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
                else:
                    message = _("Did not update GRUB bootloader (if any)")
                    self.logger.write(message + "\n")
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
                # Clonezilla doesn't check the return code, so neither does Rescuezilla
            else:
                message = "Not re-installing GRUB bootloader: Unable to find ocs-install-grub. Is Clonezilla installed?"
                self.logger.write(message + "\n")
                with self.summary_message_lock:
                    self.summary_message += message + "\n"

            if shutil.which("ocs-update-initrd") is not None:
                GLib.idle_add(self.display_status, _("Updating initramfs (if any)"), "")
                # TODO: Port Clonezilla's ocs-update-initrd bash script to Python instead of relying on Clonezilla's script
                process, flat_command_string, failed_message = Utility.run(
                   "Update initramfs (if any)",
                    ["ocs-update-initrd", "--selected-parts", dest_partition_short_dev_node_string,
                     "--selected-hd", restore_destination_drive_short_dev_node, "auto"], use_c_locale=False, logger=self.logger)
                if process.returncode == 0:
                    message = _("Successfully updated initramfs")
                    self.logger.write(message + "\n")
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
            else:
                message = "Not updating initramfs: Unable to find ocs-update-initrd. Is Clonezilla installed?"
                self.logger.write(message + "\n")
                with self.summary_message_lock:
                    self.summary_message += message + "\n"

            if self.is_overwriting_partition_table:
                # "Reinstall whole MBR (512 bytes)"
                if absolute_mbr_path:
                    process, flat_command_string, failed_message = Utility.run(
                        "Restoring the MBR data (512 bytes), i.e. executable code area + table of primary partitions + MBR signature, for " + self.restore_destination_drive,
                        ["dd", "if=" + self.image.get_absolute_mbr_path(),
                         "of=" + self.restore_destination_drive, "bs=512", "count=1"],
                        use_c_locale=False, logger=self.logger)
                    if process.returncode != 0:
                        with self.summary_message_lock:
                            self.summary_message += failed_message
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                    if not self.update_kernel_partition_table(wait_for_partition=True):
                        failed_message = _("Failed to refresh the devices' partition table. This can happen if another process is accessing the partition table.")
                        GLib.idle_add(self.completed_restore, False, failed_message)
                        return False, failed_message

                    # Shutdown the Logical Volume Manager (LVM) again -- it seems the volume groups re-activate after partition table restored for some reason.
                    # FIXME: Look into this.
                    is_successfully_shutdown, message = self._shutdown_lvm()
                    if not is_successfully_shutdown:
                        GLib.idle_add(self.completed_restore, False, message)
                        return False, message
                else:
                    print("No MBR associated with " + short_selected_image_drive_node)

                # "Updating EFI NVRAM for the boot device"
                if self.image.efi_nvram_dat_absolute_path and 'label' in self.image.normalized_sfdisk_dict['sfdisk_dict'].keys() and "gpt" == self.image.normalized_sfdisk_dict['sfdisk_dict']['label']:
                    if len(Parted.get_partitions_containing_flag(self.image.parted_dict, "bios_grub")) > 0:
                        self.logger.write("Found bios_grub flag! Skipping EFI NVRAM update.")
                    else:
                        if shutil.which("update-efi-nvram-boot-entry") is None:
                            message = "Not updating EFI NVRAM: Unable to find update-efi-nvram-boot-entry. Is Clonezilla installed?\n"
                            self.logger.write(message)
                            with self.summary_message_lock:
                                self.summary_message += message + "\n"
                        else:
                            GLib.idle_add(self.display_status, _("Updating EFI NVRAM..."))
                            # TODO: Port Clonezilla's ocs-update-initrd bash script to Python instead of relying on Clonezilla's script
                            # Unlike Clonezilla, no need to specify a -f/--efi-boot-file-info option
                            process, flat_command_string, failed_message = Utility.run(
                                "Update EFI NVRAM",
                                ["update-efi-nvram-boot-entry", "--full-path-to-efi-file", self.image.efi_nvram_dat_absolute_path, self.restore_destination_drive], use_c_locale=False,
                                logger=self.logger)
                            if process.returncode == 0:
                                message = _("Successfully updated EFI NVRAM")
                                self.logger.write(message)
                                with self.summary_message_lock:
                                    self.summary_message += message + "\n"
                            # No need to implement "get the new efi_os_label, efi_system_part_no and efi_sys_part_boot_file"
                            # because Rescuezilla doesn't operate in client/server like Clonezilla.
        elif isinstance(self.image, FsArchiverImage):
            self.logger.write("Detected FsArchiverImage")
            self.logger.write(str(self.restore_mapping_dict))

            is_unmounted, message = Utility.umount_warn_on_busy(self.restore_destination_drive)
            if not is_unmounted:
                with self.summary_message_lock:
                    self.summary_message += message + "\n"
                GLib.idle_add(self.restore_destination_drive, False, message)

            if self.requested_stop:
                GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                return False, _("User requested operation to stop.")

            image_number = 0
            for image_key in self.restore_mapping_dict.keys():
                dest_partition = self.restore_mapping_dict[image_key]['dest_key']
                is_unmounted, message = Utility.umount_warn_on_busy(dest_partition)
                if not is_unmounted:
                    self.logger.write(message)
                    with self.summary_message_lock:
                        self.summary_message += message + "\n"
                    GLib.idle_add(self.restore_destination_drive, False, message)

                image_number += 1
                self.logger.write("Going to restore " + image_key + " of image to " + self.restore_mapping_dict[image_key][
                    'dest_key'] + "\n")

                fsarchiver_restfs_cmd_list = ["fsarchiver", "restfs", self.image.absolute_path, "id="+image_key + ",dest=" + dest_partition]
                flat_command_string = Utility.print_cli_friendly(image_key + " command ", [fsarchiver_restfs_cmd_list])
                self.proc['fsarchiver_restfs_' + image_key] = subprocess.Popen(fsarchiver_restfs_cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, encoding='utf-8')

                # Process partclone output. Partclone outputs an update every 3 seconds, so processing the data
                # on the current thread, for simplicity.
                # Poll process.stdout to show stdout live
                proc_stdout = ""
                proc_stderr = ""
                while True:
                    if self.requested_stop:
                        GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                        return False, _("User requested operation to stop.")

                    output = self.proc['fsarchiver_restfs_' + image_key].stderr.readline()
                    proc_stderr += output
                    self.logger.write(output)
                    if self.proc['fsarchiver_restfs_' + image_key].poll() is not None:
                        break
                    if output:
                        temp_dict = Partclone.parse_partclone_output(output)
                        if 'completed' in temp_dict.keys():
                            GLib.idle_add(self.update_progress_bar, temp_dict['completed'] / 100.0)
                            total_progress_float = Utility.calculate_progress_ratio(
                                current_partition_completed_percentage=temp_dict['completed'] / 100.0,
                                current_partition_bytes=self.restore_mapping_dict[image_key][
                                    'estimated_size_bytes'],
                                cumulative_bytes=self.restore_mapping_dict[image_key]['cumulative_bytes'],
                                total_bytes=total_size_estimate,
                                image_number=image_number,
                                num_partitions=len(self.restore_mapping_dict.keys()))
                            GLib.idle_add(self.update_progress_bar, total_progress_float)
                        if 'remaining' in temp_dict.keys():
                            GLib.idle_add(self.update_progress_status, output)

                rc = self.proc['fsarchiver_restfs_' + image_key].poll()

                stdout, stderr = self.proc['fsarchiver_restfs_' + image_key].communicate()
                proc_stdout += stdout
                proc_stderr += stderr
                rc = self.proc['fsarchiver_restfs_' + image_key].returncode
                self.logger.write("Exit output " + str(rc) + ": " + str(proc_stdout) + "stderr " + str(proc_stderr))
                if self.proc['fsarchiver_restfs_' + image_key].returncode != 0:
                    partition_summary = _("Error restoring partition {image_key} to {destination_partition}.").format(
                        image_key=image_key,
                        destination_partition=self.restore_mapping_dict[image_key]['dest_key']) + "\n"
                    extra_info = "\nThe command used internally was:\n\n" + flat_command_string + "\n\n" + "The output of the command was: " + str(
                        output) + "\n\n" + str(proc_stderr)
                    GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                  partition_summary + extra_info)
                    with self.summary_message_lock:
                        self.summary_message += partition_summary
                    continue
                else:
                    with self.summary_message_lock:
                        self.summary_message += _(
                            "Successfully restored image partition {image} to {destination_partition}").format(
                            image=image_key, destination_partition=self.restore_mapping_dict[image_key]['dest_key']) + "\n"

                if self.requested_stop:
                    GLib.idle_add(self.completed_restore, False, _("User requested operation to stop."))
                    return False, _("User requested operation to stop.")

        GLib.idle_add(self.completed_restore, True, "")
        return True, ""

    def do_sfdisk_corrections(self, input_sfdisk_absolute_path):
        # Delete the last-lba line to fix ensure secondary GPT gets written to the correct place even when
        # destination disk differs in size [1]. Also deletes the sector-size row to maximize compatibility with
        # sfdisk backups made with util-linux-2.35.1-1 [2] (from eg more recent versions of Clonezilla) until
        # Rescuezilla has updated util-linux.
        #
        # [1] https://sourceforge.net/p/clonezilla/bugs/342/
        # [2] https://github.com/karelzak/util-linux/issues/949
        #
        # TODO: Simplify the Python code below make this happen (which was based on based [3] [4]).
        # [3] https://stackoverflow.com/a/17222971/4745097
        # [4] https://stackoverflow.com/a/6587648/4745097
        temp_dir = tempfile.gettempdir()
        corrected_sfdisk_path = os.path.join(temp_dir, 'secondary.gpt.sector.size.corrected.sfdisk.sf')
        shutil.copy2(input_sfdisk_absolute_path,
                     corrected_sfdisk_path)
        # Fix the secondary GPT partition location if the destination disk is different to the source
        last_lba_matched = re.compile("^last-lba.*").search
        sector_size_matched = re.compile("^sector-size.*").search
        with fileinput.FileInput(corrected_sfdisk_path, inplace=True) as file:
            for line in file:
                if not last_lba_matched(line) and not sector_size_matched(line):
                    # Write line to file
                    print(line, end='')
        return corrected_sfdisk_path

    def check_all_target_block_devices_exist(self):
        partition_table_message = ""
        is_all_target_block_devices_exist = True
        for image_key in self.restore_mapping_dict.keys():
            dest_part = self.restore_mapping_dict[image_key]
            p = pathlib.Path(dest_part['dest_key'])
            if p.is_block_device():
                partition_table_message += "Target partition " + dest_part['dest_key'] + " exists." + "\n"
            else:
                is_target_block_devices_exist = False
                partition_table_message += "Error target partition: " + dest_part[
                    'dest_key'] + " is not block device. Partition table may not have correctly restored." + "\n"
        return is_all_target_block_devices_exist, partition_table_message

    # Intended to be called via event thread
    def update_main_statusbar(self, message):
        context_id = self.main_statusbar.get_context_id("restore")
        self.main_statusbar.pop(context_id)
        self.main_statusbar.push(context_id, message)

    # Intended to be called via event thread
    def update_progress_status(self, message):
        self.restore_progress_status.set_text(message)
        self.clone_progress_status.set_text(message)

    # Intended to be called via event thread
    def update_progress_bar(self, fraction):
        if self.logger is not None:
            self.logger.write("Updating progress bar to " + str(fraction) + "\n")
        self.restore_progress.set_fraction(fraction)
        self.clone_progress.set_fraction(fraction)

    # Expected to run on GTK event thread
    def completed_restore(self, succeeded, message):
        # Clear messages
        self.update_progress_status("")
        self.main_statusbar.remove_all(self.main_statusbar.get_context_id("restore"))
        if not self.is_cloning:
            restore_timeend = datetime.now()
            duration_minutes = Utility.get_human_readable_minutes_seconds((restore_timeend - self.restore_timestart).total_seconds())

            if succeeded:
                print("Success")
            else:
                with self.summary_message_lock:
                    self.summary_message += message + "\n"
                error = ErrorMessageModalPopup(self.builder, message)
                print("Failure")
            with self.summary_message_lock:
                self.summary_message += "\n" + _("Operation took {num_minutes} minutes.").format(num_minutes=duration_minutes) + "\n"
                post_task_action = Utility.get_combobox_key(self.builder.get_object("restore_step6_perform_action_combobox"))
                if post_task_action != "DO_NOTHING":
                    if succeeded:
                        has_scheduled, msg = Utility.schedule_shutdown_reboot(post_task_action)
                        self.summary_message += "\n" + msg
                    else:
                        self.summary_message += "\n" + _("Shutdown/Reboot cancelled due to errors.")
        if self.logger:
            self.logger.close()
        with self.restore_in_progress_lock:
            self.restore_in_progress = False
        self.populate_summary_page()
        if not self.is_cloning:
            self.completed_callback(succeeded)

    def populate_summary_page(self):
        with self.summary_message_lock:
            self.logger.write("Populating summary page with:\n\n" + self.summary_message)
            text_to_display = """<b>{heading}</b>

{message}""".format(heading=_("Restore Summary"), message=GObject.markup_escape_text(self.summary_message))
        self.builder.get_object("restore_step7_summary_program_defined_text").set_markup(text_to_display)
