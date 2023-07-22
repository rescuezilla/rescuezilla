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
import os
import queue
import shutil
import signal
import subprocess
import threading
import traceback
from datetime import datetime
from queue import Empty, Queue
from time import sleep

import gi

import utility
from parser.apart_gtk_image import ApartGtkImage
from parser.fogproject_image import FogProjectImage
from parser.foxclone_image import FoxcloneImage
from parser.fsarchiver_image import FsArchiverImage
from parser.qemu_image import QemuImage
from parser.redorescue_image import RedoRescueImage
from wizard_state import IMAGE_EXPLORER_DIR, MOUNTABLE_NBD_DEVICE, DECOMPRESSED_NBD_DEVICE, JOINED_FILES_NBD_DEVICE, \
    QEMU_NBD_NBD_DEVICE

gi.require_version("Gtk", "3.0")

from parser.clonezilla_image import ClonezillaImage
from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import ErrorMessageModalPopup, Utility, _, PleaseWaitModalPopup

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


# Mount a Clonezilla image using partclone-nbd and nbdkit (and in future, partclone-utils).
#
# This feature heavily relies on the Linux 'nbd' (Network Block Device) module, and the very powerful "nbdkit" server.
# It is highly recommended Rescuezilla developers unfamiliar with NBD to go and watch the first 7 minutes of this video:
# https://www.youtube.com/watch?v=9E5A608xJG0
#
# The virtual concatenation of (potentially hundreds) of 4GB split files, and the mounting of partclone images
# is near instantaneous. Accessing 'xz' compressed archives and uncompressed archives is also very fast.
# However, accessing gzip compressed archives is VERY slow. This format happens to be the default in Clonezilla and
# Rescuezilla. There's apparently little that can be done about this other than switching to a format more suited to
# random access. From `man nbdkit-gzip-filter`: "Note that gzip files are not very good for random access in large files
# because seeking to a position in the gzip file involves decompressing all data before that point in the file."
#
# TODO: Add support to explore more compression formats used by Clonezilla (currently only xz, gzip and uncompressed)
# TODO: Switch to partclone-utils (from partclone-nbd) in order to support 'ntfsclone' images in addition to 'partclone'
class ImageExplorerManager:
    def __init__(self, builder, image_explorer_partition_selection_list,
                 set_support_information_linkbutton_visible, set_patreon_call_to_action_visible):
        self.image_explorer_in_progress = False
        self.is_partition_mounted = False
        self.builder = builder
        self.main_statusbar = self.builder.get_object("main_statusbar")
        self.duration_label = self.builder.get_object("image_explorer_operation_duration_label")
        self.image_explorer_partition_selection_list = image_explorer_partition_selection_list
        self.restore_partition_treeview = self.builder.get_object("restore_step4_image_partition_treeview")
        # FIXME: Remove need to passing the support info / patreon visibility functions for improved abstraction
        self.set_support_information_linkbutton_visible = set_support_information_linkbutton_visible
        self.set_patreon_call_to_action_visible = set_patreon_call_to_action_visible
        # proc dictionary
        self.proc = collections.OrderedDict()
        self.requested_stop_lock = threading.Lock()
        self.requested_stop = False
        self.image_explorer_in_progress = False
        self.qemu_nbd_process_queue = Queue()
        # The mount and unmount calls may take place on different threads due to GTK button press events, so communicate
        # the pid via a queue.
        self.partclone_nbd_process_queue = Queue()
        self.nbdkit_join_process_queue = Queue()
        self.nbdkit_decompress_process_queue = Queue()

    def is_image_explorer_in_progress(self):
        return self.image_explorer_in_progress

    def cancel_image_explorer(self):
        with self.requested_stop_lock:
            self.requested_stop = True
        self.image_explorer_in_progress = False
        return

    # Intended to be called via event thread
    def update_main_statusbar(self, message):
        context_id = self.main_statusbar.get_context_id("image_explorer")
        self.main_statusbar.pop(context_id)
        self.main_statusbar.push(context_id, message)

    # Based on the PartitionsToRestore function
    def populate_partition_selection_table(self, selected_image):
        self.image_explorer_partition_selection_list.clear()
        self.builder.get_object("button_mount").set_sensitive(False)

        self.selected_image = selected_image
        if isinstance(self.selected_image, ClonezillaImage) or isinstance(self.selected_image, RedoBackupLegacyImage)\
                or isinstance(self.selected_image, FogProjectImage) or isinstance(self.selected_image, RedoRescueImage)\
                or isinstance(self.selected_image, FoxcloneImage) or isinstance(self.selected_image, ApartGtkImage):
            for image_format_dict_key in self.selected_image.image_format_dict_dict.keys():
                print("ClonezillaImage contains partition " + image_format_dict_key)
                if self.selected_image.does_image_key_belong_to_device(image_format_dict_key):
                    if self.selected_image.image_format_dict_dict[image_format_dict_key]['is_lvm_logical_volume']:
                        human_friendly_partition_name = image_format_dict_key
                        flat_description = "Logical Volume " + image_format_dict_key + ": "\
                                           + self.selected_image.flatten_partition_string(image_format_dict_key)
                    elif isinstance(self.selected_image, ApartGtkImage):
                        human_friendly_partition_name = image_format_dict_key
                        flat_description = image_format_dict_key + ": " + self.selected_image.flatten_partition_string(image_format_dict_key)
                    else:
                        image_base_device_node, image_partition_number = Utility.split_device_string(
                            image_format_dict_key)
                        human_friendly_partition_name = "#" + str(
                            image_partition_number) + " (" + image_format_dict_key + ")"
                        flat_description = str(
                            image_partition_number) + ": " + self.selected_image.flatten_partition_string(image_format_dict_key)
                    self.image_explorer_partition_selection_list.append(
                        [image_format_dict_key, human_friendly_partition_name, flat_description])
        elif isinstance(self.selected_image, FsArchiverImage):
            for fs_key in self.selected_image.fsa_dict['filesystems'].keys():
                long_device_node = self.selected_image.fsa_dict['filesystems'][fs_key]['original_long_device_node']
                human_friendly_partition_name = "#" + str(fs_key) + " (" + long_device_node + ")"
                flat_description = str(fs_key) + ": " + self.selected_image.flatten_partition_string(
                    fs_key)
                self.image_explorer_partition_selection_list.append(
                    [fs_key, human_friendly_partition_name, flat_description])
        elif isinstance(self.selected_image, QemuImage):
            for long_device_node in self.selected_image.normalized_sfdisk_dict['sfdisk_dict']['partitions'].keys():
                image_base_device_node, image_partition_number = Utility.split_device_string(long_device_node)
                human_friendly_partition_name = "#" + str(image_partition_number) + " (" + long_device_node + ")"
                flat_description = str(image_partition_number) + ": " + self.selected_image.flatten_partition_string(
                    long_device_node)
                self.image_explorer_partition_selection_list.append(
                    [long_device_node, human_friendly_partition_name, flat_description])

    # Sets sensitivity of all elements on the Image Explorer page
    def set_parts_of_image_explorer_page_sensitive(self, is_sensitive):
        self.builder.get_object("image_explorer_image_partition_treeview").set_sensitive(is_sensitive)
        self.builder.get_object("button_back").set_sensitive(is_sensitive)
        self.builder.get_object("button_next").set_sensitive(is_sensitive)

    def get_mounted_state(self):
        return self.is_partition_mounted

    def set_mounted_state(self, is_mounted):
        if is_mounted:
            self.is_partition_mounted = True
            self.builder.get_object("button_mount").set_label(_("Unmount"))
            self.set_parts_of_image_explorer_page_sensitive(False)
            self.builder.get_object("button_open_file_manager").set_sensitive(True)
        else:
            self.is_partition_mounted = False
            self.builder.get_object("button_mount").set_label(_("Mount"))
            self.set_parts_of_image_explorer_page_sensitive(True)
            self.builder.get_object("button_open_file_manager").set_sensitive(False)

    def _post_backup_image_unmount_callback(self, is_success, error_message=""):
        if not is_success:
            error = ErrorMessageModalPopup(self.builder, error_message)
            self.duration_label.set_label("")
            self.duration_label.set_visible(False)
            self.set_support_information_linkbutton_visible(True)
            self.set_patreon_call_to_action_visible(False)
        else:
            self.set_mounted_state(False)
            self.duration_label.set_label("")
            self.duration_label.set_visible(False)
            self.set_support_information_linkbutton_visible(False)
            self.set_patreon_call_to_action_visible(True)

    def _post_backup_image_mount_callback(self, is_success, message=""):
        if not is_success:
            error = ErrorMessageModalPopup(self.builder, message)
            self.duration_label.set_label("")
            self.duration_label.set_visible(False)
            self.set_support_information_linkbutton_visible(True)
            self.set_patreon_call_to_action_visible(False)
        else:
            self.duration_label.set_label(message)
            self.duration_label.set_visible(True)
            self.set_mounted_state(True)
            self.set_support_information_linkbutton_visible(False)
            self.set_patreon_call_to_action_visible(True)

    @staticmethod
    # This `man pgrep` patterns needs to be kept in sync with the process being used.
    def pop_and_kill(process_name, process_queue, pgrep_pattern):
        if process_queue is not None:
            while not process_queue.empty():
                try:
                    process = process_queue.get_nowait()
                    print("Kill " + process_name + " with pid " + str(process.pid) + " with SIGTERM")
                    process.send_signal(signal.SIGTERM)
                    try:
                        # Wait for cleanup
                        process.wait(10)
                    except subprocess.TimeoutExpired:
                        print(
                            "Timeout expired, kill " + process_name + " with pid " + str(process.pid) + " with SIGKILL")
                        # Send kill signal
                        process.send_signal(signal.SIGKILL)
                except queue.Empty:
                    break
        else:
            # Kill all processes matching the pattern. Sending SIGKILL will leave temporary files without cleaning up,
            # which for the nbdkit decompression may include very large files.
            process, flat_command_string, failed_message = Utility.run(
                "Kill all " + process_name + " processes with SIGKILL",
                ["pkill", "--signal", "SIGKILL", "--full", pgrep_pattern],
                use_c_locale=True)
            if process.returncode != 0 and process.returncode != 1:
                return False, failed_message
        return True, ""

    @staticmethod
    def _do_unmount(destination_path, join_process_queue=None, decompress_process_queue=None,
                    partclone_nbd_process_queue=None, is_deassociate_qemu_nbd_device=True):
        # Ensure nbd-kernel module loaded (required for nbd-client -disconnect)
        process, flat_command_string, failed_message = Utility.run("Loading NBD kernel module",
                                                                   ["modprobe", "nbd"],
                                                                   use_c_locale=True)
        if process.returncode != 0:
            return False, failed_message

        # Unmount and cleanup in case a previous invocation of Rescuezilla didn't cleanup.
        is_unmounted, message = Utility.umount_warn_on_busy(destination_path)
        if not is_unmounted:
            return False, message

        if is_deassociate_qemu_nbd_device:
            is_success, message = QemuImage.deassociate_nbd(QEMU_NBD_NBD_DEVICE)
            if not is_success:
                return False, message

        is_success, message = ImageExplorerManager.pop_and_kill("partclone-nbd", partclone_nbd_process_queue,
                                                                "partclone-nbd")
        if not is_success:
            return False, message

        process, flat_command_string, failed_message = Utility.run("Disconnect nbd decompress association",
                                                                   ["nbd-client", "-disconnect",
                                                                    DECOMPRESSED_NBD_DEVICE],
                                                                   use_c_locale=True)
        if process.returncode != 0:
            return False, failed_message

        is_success, message = ImageExplorerManager.pop_and_kill("nbdkit decompress", decompress_process_queue,
                                                                "nbdkit.*split")
        if not is_success:
            return False, message

        process, flat_command_string, failed_message = Utility.run("Disconnect nbd association",
                                                                   ["nbd-client", "-disconnect",
                                                                    JOINED_FILES_NBD_DEVICE],
                                                                   use_c_locale=True)
        if process.returncode != 0:
            return False, failed_message

        is_success, message = ImageExplorerManager.pop_and_kill("nbdkit join", join_process_queue,
                                                                "nbdkit.*(gzip|file)")
        if not is_success:
            return False, message

        print("Successfully requested any partclone-nbd images to unmount.")
        return True, ""

    def get_partition_compression(self, selected_partition_key):
        if 'compression' in self.selected_image.image_format_dict_dict[selected_partition_key].keys():
            return self.selected_image.image_format_dict_dict[selected_partition_key]['compression']
        else:
            return None

    def get_partition_type(self, selected_partition_key):
        if 'type' in self.selected_image.image_format_dict_dict[selected_partition_key].keys():
            return self.selected_image.image_format_dict_dict[selected_partition_key]['type']
        else:
            return None

    def mount_partition(self, selected_partition_key):
        self.image_explorer_in_progress = True
        with self.requested_stop_lock:
            self.requested_stop = False

        if self.is_partition_mounted:
            # Unmount partition
            please_wait_popup = PleaseWaitModalPopup(self.builder, title=_("Please wait..."),
                                                     message=_("Unmounting: {path}").format(path=selected_partition_key),
                                                     on_close_callback=self.cancel_image_explorer)
            please_wait_popup.show()
            self.mount_thread = threading.Thread(target=self._do_unmount_wrapper,
                                                 args=(
                                                     please_wait_popup, self._post_backup_image_unmount_callback,
                                                     IMAGE_EXPLORER_DIR))
            self.mount_thread.daemon = True
            self.mount_thread.start()
        else:
            mount_msg = _(
                "Mounting as read-only...") + "\n\nFor 'gzip' compressed images often the entire backup image needs to be decompressed to a temporary file before a single file can be accessed.\nFor very large backup images this MAY TAKE HOURS depending on the speed of your computer.\n\nFor near-instantaneous file access, a future version of Rescuezilla may switch the default compression away from 'gzip'.\n\nTo cancel the mount operation close this dialog box."
            please_wait_popup = PleaseWaitModalPopup(self.builder, title=_("Please wait..."), message=mount_msg,
                                                     on_close_callback=self.cancel_image_explorer)
            please_wait_popup.show()
            thread = threading.Thread(target=self._do_mount_command, args=(
                please_wait_popup, self._post_backup_image_mount_callback, self.selected_image, selected_partition_key,
                IMAGE_EXPLORER_DIR,))
            thread.daemon = True
            thread.start()

    def _on_image_partition_mount_completed_callback(self, is_success):
        if is_success:
            self.set_support_information_linkbutton_visible(False)
            self.set_patreon_call_to_action_visible(True)
            self.set_parts_of_image_explorer_page_sensitive(False)
        else:
            self.set_support_information_linkbutton_visible(True)
            self.set_patreon_call_to_action_visible(False)
            self.set_parts_of_image_explorer_page_sensitive(True)

    def _do_unmount_wrapper(self, please_wait_popup, callback, destination_path):
        try:
            returncode, failed_message = ImageExplorerManager._do_unmount(destination_path,
                                                                          self.nbdkit_join_process_queue,
                                                                          self.nbdkit_decompress_process_queue,
                                                                          self.partclone_nbd_process_queue)
            if not returncode:
                print(failed_message)
                GLib.idle_add(callback, False, failed_message)
                GLib.idle_add(please_wait_popup.destroy)
                return
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(callback, False, "Error unmounting folder: " + tb)
            GLib.idle_add(please_wait_popup.destroy)
            return
        GLib.idle_add(callback, True, "")
        GLib.idle_add(please_wait_popup.destroy)
        return

    # FIXME: This logic should be able to be simplified.
    def _check_stop_and_cleanup(self, please_wait_popup, callback, destination_path):
        if self.is_stop_requested():
            returncode, failed_message = ImageExplorerManager._do_unmount(destination_path,
                                                                          self.nbdkit_join_process_queue,
                                                                          self.nbdkit_decompress_process_queue,
                                                                          self.partclone_nbd_process_queue)
            if not returncode:
                print(failed_message)
                GLib.idle_add(callback, False, _("User requested operation to stop.") + "\n\n" + failed_message)
                GLib.idle_add(please_wait_popup.destroy)
            else:
                GLib.idle_add(callback, False, _("User requested operation to stop."))
                GLib.idle_add(please_wait_popup.destroy)
            return True
        else:
            return False

    def is_stop_requested(self):
        with self.requested_stop_lock:
            return self.requested_stop

    def _do_mount_command(self, please_wait_popup, callback, image, partition_key, destination_path):
        env = Utility.get_env_C_locale()
        backup_timestart = datetime.now()
        try:
            if not os.path.exists(destination_path) and not os.path.isdir(destination_path):
                os.mkdir(destination_path, 0o755)

            if shutil.which("nbdkit") is None:
                GLib.idle_add(callback, False, "nbdkit not found")
                GLib.idle_add(please_wait_popup.destroy)
                return

            if self._check_stop_and_cleanup(please_wait_popup, callback, destination_path):
                return

            GLib.idle_add(please_wait_popup.set_secondary_label_text, "Loading Network Block Device driver (step 1/5)")
            # Ensure nbd-kernel module loaded
            process, flat_command_string, failed_message = Utility.interruptable_run("Loading NBD kernel module",
                                                                                     ["modprobe", "nbd"],
                                                                                     use_c_locale=True,
                                                                                     is_shutdown_fn=self.is_stop_requested)
            if process.returncode != 0:
                print(failed_message)
                GLib.idle_add(callback, False, failed_message)
                GLib.idle_add(please_wait_popup.destroy)
                return

            # Unmount any previous
            is_unmount_success, failed_message = self._do_unmount(destination_path)
            if not is_unmount_success:
                print(failed_message)
                GLib.idle_add(callback, False, failed_message)
                GLib.idle_add(please_wait_popup.destroy)
                return

            mount_device = MOUNTABLE_NBD_DEVICE
            compression = ""
            image_file_list = []
            if isinstance(self.selected_image, ClonezillaImage) or isinstance(self.selected_image, RedoBackupLegacyImage) \
                    or isinstance(self.selected_image, FogProjectImage) or isinstance(self.selected_image, RedoRescueImage) \
                    or isinstance(self.selected_image, FoxcloneImage) or isinstance(self.selected_image, ApartGtkImage):
                # Clonezilla images support gzip bzip2 lzo lzma xz lzip lrzip lz4 zstd and uncompressed.
                if 'absolute_filename_glob_list' not in image.image_format_dict_dict[partition_key].keys():
                    GLib.idle_add(callback, False, "No associated image files found")
                    GLib.idle_add(please_wait_popup.destroy)
                    return
                image_file_list = image.image_format_dict_dict[partition_key]['absolute_filename_glob_list']
                compression = image.image_format_dict_dict[partition_key]['compression']
                incompatible_image_message = ""
                if compression != "gzip" and compression != "xz" and compression != "uncompressed":
                    incompatible_image_message = "Currently only supports gzip, xz and uncompressed images, not: " + compression
                    incompatible_image_message += "\nSupport for more compression types coming in a future release."
                if 'type' in image.image_format_dict_dict[partition_key].keys():
                    image_type = image.image_format_dict_dict[partition_key]['type']
                    if image_type != 'partclone':
                        incompatible_image_message = "Currently only supports partclone images, not: " + image_type
                        incompatible_image_message += "\nSupport for ntfsclone images coming in a future release."
                if incompatible_image_message != "":
                    GLib.idle_add(callback, False,
                                  "Image Explorer (beta) failed to mount image:\n\n" + incompatible_image_message)
                    GLib.idle_add(please_wait_popup.destroy)
                    return
            elif isinstance(image, QemuImage):
                image.associate_nbd(QEMU_NBD_NBD_DEVICE)
                base_device_node, partition_number = Utility.split_device_string(partition_key)
                mount_device = Utility.join_device_string(QEMU_NBD_NBD_DEVICE, partition_number)
            if not isinstance(image, QemuImage):
                # Concatenate the split partclone images into a virtual block device using nbdkit. This step is fast
                # because it's just logical mapping within the nbdkit process. In other words "lazy-evaulation: no
                # concatenation is actually occurring.
                #
                # nbdkit's "--filter=" arguments can be used to decompress requested blocks on-the-fly in a single nbdkit
                # invokation. However for flexibility with the older nbdkit version in Ubuntu 20.04 (see below),
                # and the limited number of compression filters even in recent nbdkit versions, Rescuezilla does this in
                # two steps: joining the files is a different step to decompressing the files. This approach provides
                # greater flexibility for alternative decompression utilities such as perhaps `archivemount` or AVFS.

                # Launches nbdkit using the 'split' plugin (`man nbdkit-split-plugin`) to concatenate the files.
                # The concatenated compressed image file is almost certainly not aligned to a 512-byte or 4096-byte block
                # boundary. To force the partially-filled final block to always be served up, using the truncate filter
                # (`man nbdkit-truncate-filter`) with the "round-up" parameter to pad that final block with zeroes.
                nbdkit_join_cmd_list = ["nbdkit", "--no-fork", "--readonly", "--filter=truncate",
                                        "split"] + image_file_list + [
                                           "round-up=512"]
                flat_command_string = Utility.print_cli_friendly(
                    "Create nbd server using nbdkit to dynamically concatenate (possibly hundreds) of 4 gigabyte pieces (and zero-pad the final partially-filled block to the 512-byte block boundary)",
                    [nbdkit_join_cmd_list])
                GLib.idle_add(please_wait_popup.set_secondary_label_text,
                              "Joining all the split image files (this may take a while) (step 2/5")
                # Launch the server (long-lived process so PID/exit code/stdout/stderr management is especially important)
                nbdkit_join_process = subprocess.Popen(nbdkit_join_cmd_list,
                                                       stdout=subprocess.PIPE,
                                                       env=env,
                                                       encoding='utf-8')
                print("Adding join process with pid " + str(nbdkit_join_process.pid) + " to queue")
                self.nbdkit_join_process_queue.put(nbdkit_join_process)

                if self._check_stop_and_cleanup(please_wait_popup, callback, destination_path):
                    return

                # Connect the /dev/nbdN device node to the NBD server launched earlier.
                nbdclient_connect_cmd_list = ["nbd-client", "-block-size", "512", "localhost", JOINED_FILES_NBD_DEVICE]
                is_success, message = Utility.retry_run(short_description="Associating the nbdkit server process being used for dynamic CONCATENATION with the nbd device node: " + JOINED_FILES_NBD_DEVICE,
                                                        cmd_list=nbdclient_connect_cmd_list,
                                                        expected_error_msg="Error: Socket failed: Connection refused",
                                                        retry_interval_seconds=1,
                                                        timeout_seconds=5,
                                                        is_shutdown_fn=self.is_stop_requested)
                if not is_success:
                    failed_message = message
                    is_unmount_success, unmount_failed_message = self._do_unmount(destination_path,
                                                                                  self.nbdkit_join_process_queue,
                                                                                  self.nbdkit_decompress_process_queue,
                                                                                  self.partclone_nbd_process_queue)
                    if not is_unmount_success:
                        failed_message += "\n\n" + unmount_failed_message
                    GLib.idle_add(callback, False, failed_message)
                    GLib.idle_add(please_wait_popup.destroy)
                    return

                if self._check_stop_and_cleanup(please_wait_popup, callback, destination_path):
                    return

                nbd_compression_filter_and_plugin = []
                if "xz" == compression:
                    # In the xz case, use the file plugin and the xz filter
                    nbd_compression_filter_and_plugin = ["--filter=xz", "file"]
                elif "gzip" == compression:
                    # In the gzip case, use the gzip plugin. This is because Ubuntu 20.04 (Focal) still use nbdkit v1.16
                    # which had not yet removed the gzip plugin and replaced it with a gzip filter [1] [2]
                    # [1] https://bugs.launchpad.net/ubuntu/+source/nbdkit/+bug/1904554
                    # [2] https://packages.ubuntu.com/focal/nbdkit
                    nbd_compression_filter_and_plugin = ["gzip"]
                elif "uncompressed" == compression:
                    # In the uncompressed case, use the file plugin without any compression filters (passthrough). This
                    # unnecessary extra layer for uncompressed data is inefficient in theory (and possibly in practice) but
                    # this approach makes the code simpler and the uncompressed case is still way faster than compressed.
                    nbd_compression_filter_and_plugin = ["file"]
                else:
                    # Clonezilla still has more compression formats: bzip2 lzo lzma lzip lrzip lz4 zstd
                    # TODO: This codepath shouldn't ever be hit currently due to being dealt with earlier.
                    # TODO: Use the FUSE-based tools archivemount and/or AVFS to provide at least some basic/slow fallback
                    # TODO: support for these compression formats widely used by Expert Mode Clonezilla users.
                    # During testing there was a 'permission denied' error using archivemount with nbd block devices,
                    # even after settings the correct configuration in /etc/fuse.conf and using `-o allow_root`.
                    is_unmount_success, unmount_failed_message = self._do_unmount(destination_path,
                                                                                  self.nbdkit_join_process_queue,
                                                                                  self.nbdkit_decompress_process_queue,
                                                                                  self.partclone_nbd_process_queue)
                    if not is_unmount_success:
                        failed_message += "\n\n" + unmount_failed_message
                    failed_message = "Image Explorer (beta) doesn't yet support image compression: " + compression
                    GLib.idle_add(callback, False, failed_message)
                    GLib.idle_add(please_wait_popup.destroy)
                    return

                # Launches nbdkit using eg, the 'file' plugin (`man nbdkit-file-plugin`) with a specific decompression
                # filter (eg, --filter=xz) to dynamically decompress the concatenated image being served on an /dev/nbdN
                # device node. Again using the truncate filter to zero pad to the nearest 512-byte block boundary.
                # Uses a non-standard port to avoid conflicting with earlier nbdkit usage.
                port = "10810"
                nbdkit_decompress_cmd_list = ["nbdkit", "--no-fork", "--readonly", "--port", "10810",
                                              "--filter=truncate"] + nbd_compression_filter_and_plugin + [
                                                 "file=" + JOINED_FILES_NBD_DEVICE, "round-up=512"]
                flat_command_string = Utility.print_cli_friendly(
                    "Create nbd server using nbdkit to dynamically decompress the concatenated image (and zero-pad the final partially-filled block to the 512-byte block boundary)",
                    [nbdkit_decompress_cmd_list])
                GLib.idle_add(please_wait_popup.set_secondary_label_text,
                              "Decompressing the combined partclone image file (this may take while) (step 3/5)")
                nbdkit_decompress_process = subprocess.Popen(nbdkit_decompress_cmd_list,
                                                             stdout=subprocess.PIPE,
                                                             env=env,
                                                             encoding='utf-8')

                if self._check_stop_and_cleanup(please_wait_popup, callback, destination_path):
                    return
                print("Adding decompress process with pid " + str(nbdkit_decompress_process.pid) + " to queue")
                self.nbdkit_decompress_process_queue.put(nbdkit_decompress_process)

                nbdclient_connect_cmd_list = ["nbd-client", "-block-size", "512", "localhost", port, DECOMPRESSED_NBD_DEVICE]
                is_success, message = Utility.retry_run(short_description="Associating the nbdkit server process being used for dynamic DECOMPRESSION with the nbd device node. For gzip data this may take a while (as it effectively decompresses entire archive): " + DECOMPRESSED_NBD_DEVICE,
                                                        cmd_list=nbdclient_connect_cmd_list,
                                                        expected_error_msg="Error: Socket failed: Connection refused",
                                                        retry_interval_seconds=1,
                                                        timeout_seconds=5,
                                                        is_shutdown_fn=self.is_stop_requested)

                if not is_success:
                    failed_message = message
                    is_unmount_success, unmount_failed_message = self._do_unmount(destination_path,
                                                                                  self.nbdkit_join_process_queue,
                                                                                  self.nbdkit_decompress_process_queue,
                                                                                  self.partclone_nbd_process_queue)
                    if not is_unmount_success:
                        failed_message += "\n\n" + unmount_failed_message
                    GLib.idle_add(callback, False, failed_message)
                    GLib.idle_add(please_wait_popup.destroy)
                    return

                if self._check_stop_and_cleanup(please_wait_popup, callback, destination_path):
                    return

                # TODO: Handle ntfsclone via partclone-utils' imagemount
                # TODO: Some dd images may be accessible using standard `mount` cal)l
                partclone_nbd_mount_cmd_list = ["partclone-nbd", "-d", MOUNTABLE_NBD_DEVICE, "-c", DECOMPRESSED_NBD_DEVICE]
                partclone_nbd_flat_command_string = Utility.print_cli_friendly(
                    "Processing partclone image with partclone-nbd:",
                    [partclone_nbd_mount_cmd_list])

                GLib.idle_add(please_wait_popup.set_secondary_label_text,
                              "Processing image with partclone-nbd (this may take a while) (step 4/5)")
                partclone_nbd_process = subprocess.Popen(partclone_nbd_mount_cmd_list,
                                                         stdout=subprocess.PIPE,
                                                         stderr=subprocess.PIPE,
                                                         env=env)

                print("Adding partclone-nbd process with pid " + str(partclone_nbd_process.pid) + " to queue")
                self.partclone_nbd_process_queue.put(partclone_nbd_process)
                # Sentinal value for successful partclone-nbd mount. partclone-nbd is launched with C locale env, so this
                # string will match even for non-English locales.
                partclone_nbd_ready_msg = "[ INF ] Waiting for requests ..."

                # Poll the partclone-nbd stdout until the ready message has been received.
                # This relies on partclone-nbd exiting immediately if an error is generated, if not, an infinite loop will
                # result until the timeout is hit.
                # TODO: A future translation of partclone-nbd may break this on non-English languages
                mounted_successfully = False
                queue = Utility.nonblocking_subprocess_pipe_queue(partclone_nbd_process)
                partclone_nbd_output_list = []
                while True:
                    if self.is_stop_requested():
                        partclone_nbd_process.terminate()
                        # FIXME: Might need longer sleep?
                        sleep(1)
                        partclone_nbd_process.kill()
                        self._check_stop_and_cleanup(please_wait_popup, callback, destination_path)
                        return
                    try:
                        line = queue.get(timeout=0.1)
                    except Empty:
                        continue
                    else:
                        print(line)
                        line = line.decode("utf-8")
                        partclone_nbd_output_list += [line]
                        line = line.strip()
                        m = utility.REMatcher(line)
                        if m.match(r".*Waiting for requests.*"):
                            print("Detected partclone-nbd mount is ready!")
                            mounted_successfully = True
                            break
                    rc = partclone_nbd_process.poll()
                    if rc is not None:
                        break

                if not mounted_successfully:
                    partclone_nbd_flat_command_string = ""
                    for line in partclone_nbd_output_list:
                        partclone_nbd_flat_command_string += line
                    failed_message = "Unable to process image using partclone-nbd:\n\n" + partclone_nbd_flat_command_string + "\n\n"
                    if self.is_stop_requested():
                        self._do_unmount_wrapper(please_wait_popup, callback, destination_path)
                        failed_message += "\n" + _("User requested operation to stop.")
                    is_unmount_success, unmount_failed_message = self._do_unmount(destination_path,
                                                                                  self.nbdkit_join_process_queue,
                                                                                  self.nbdkit_decompress_process_queue,
                                                                                  self.partclone_nbd_process_queue)
                    if not is_unmount_success:
                        failed_message += "\n\n" + unmount_failed_message
                    GLib.idle_add(callback, False, failed_message)
                    GLib.idle_add(please_wait_popup.destroy)
                    return

                if self._check_stop_and_cleanup(please_wait_popup, callback, destination_path):
                    return

            mount_cmd_list = ["mount", "-o", "ro", mount_device, destination_path]
            GLib.idle_add(please_wait_popup.set_secondary_label_text,
                          "Mounting image (this may take a while) (step 5/5)")
            process, flat_command_string, failed_message = Utility.interruptable_run("Mount ", mount_cmd_list,
                                                                                     use_c_locale=False,
                                                                                     is_shutdown_fn=self.is_stop_requested)
            if process.returncode != 0:
                is_unmount_success, unmount_failed_message = self._do_unmount(destination_path,
                                                                              self.nbdkit_join_process_queue,
                                                                              self.nbdkit_decompress_process_queue,
                                                                              self.partclone_nbd_process_queue)
                if not is_unmount_success:
                    failed_message += "\n\n" + unmount_failed_message
                GLib.idle_add(callback, False, failed_message)
                GLib.idle_add(please_wait_popup.destroy)
                return

            if self._check_stop_and_cleanup(please_wait_popup, callback, destination_path):
                return

            backup_timeend = datetime.now()
            duration_minutes = Utility.get_human_readable_minutes_seconds((backup_timeend - backup_timestart).total_seconds())
            duration_message = _("Operation took {num_minutes} minutes.").format(
                num_minutes=duration_minutes)
            GLib.idle_add(callback, True, duration_message)
            GLib.idle_add(please_wait_popup.destroy)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(callback, False, "Error mounting folder: " + tb)
            GLib.idle_add(please_wait_popup.destroy)
            # Cleanup just in case
            is_unmount_success, unmount_failed_message = self._do_unmount(destination_path,
                                                                          self.nbdkit_join_process_queue,
                                                                          self.nbdkit_decompress_process_queue,
                                                                          self.partclone_nbd_process_queue)
            if not is_unmount_success:
                print("Unmount failed " + unmount_failed_message)
