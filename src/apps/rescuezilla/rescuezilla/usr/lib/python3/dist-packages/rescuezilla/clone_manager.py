# ----------------------------------------------------------------------
#   Copyright (C) 2003-2025 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2021-2025 Rescuezilla.com <rescuezilla@gmail.com>
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
import shutil
import tempfile
import threading
import traceback
from datetime import datetime
from utility import Utility, _
from ui_manager import UiManager
from parser.metadata_only_image import MetadataOnlyImage
from parser.qemu_image import QemuImage
from wizard_state import QEMU_NBD_NBD_DEVICE

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib  # noqa: E402


# Signals should automatically propagate to processes called with subprocess.run().


# The CloneManager leverages the BackupManager and RestoreManager as much as possible.
class CloneManager:
    def __init__(self, ui_manager: UiManager, backup_manager, restore_manager):
        self.ui_manager = ui_manager
        self.clone_in_progress_lock = threading.Lock()
        self.clone_in_progress = False
        self.backup_manager = backup_manager
        self.restore_manager = restore_manager
        # proc dictionary
        self.proc = collections.OrderedDict()
        self.requested_stop = False

    def is_clone_in_progress(self):
        with self.clone_in_progress_lock:
            return self.clone_in_progress

    def start_clone(
        self,
        image,
        clone_destination_drive,
        clone_mapping_dict,
        drive_state,
        is_overwriting_partition_table,
        is_rescue,
        completed_callback,
        on_separate_thread=True,
    ):
        self.clone_timestart = datetime.now()
        self.image = image
        self.clone_destination_drive = clone_destination_drive
        self.clone_mapping_dict = clone_mapping_dict
        self.is_overwriting_partition_table = is_overwriting_partition_table
        self.is_rescue = is_rescue
        self.completed_callback = completed_callback
        self.ui_manager.update_progress_bar(fraction=0)
        # Entire machine's drive state
        # TODO: This is a crutch that ideally will be removed. It's very bad from an abstraction perspective, and
        # TODO: clear abstractions is important for ensuring correctness of the backup/restore operation
        self.system_drive_state = drive_state
        self.temp_dir = os.path.join(
            tempfile.gettempdir(), "rescuezilla.clone.temp.data"
        )
        print("Selected temp dir " + self.temp_dir)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        with self.clone_in_progress_lock:
            self.clone_in_progress = True
        if on_separate_thread:
            thread = threading.Thread(target=self.do_clone_wrapper)
            thread.daemon = True
            thread.start()
        else:
            self.do_clone()

    # Intended to be called via event thread
    # Sending signals to process objects on its own thread. Relying on Python GIL.
    # TODO: Threading practices here need overhaul. Use threading.Lock() instead of GIL
    def cancel_clone(self):
        GLib.idle_add(self.backup_manager.cancel_backup)
        GLib.idle_add(self.restore_manager.cancel_restore)
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
                except Exception:
                    print("Error killing process. (Maybe already dead?)")
        with self.clone_in_progress_lock:
            self.clone_in_progress = False
        self.completed_clone(False, _("Operation cancelled by user."))

    """def display_status(self, msg1, msg2):
        GLib.idle_add(self.update_clone_progress_status, msg1 + "\n" + msg2)
        GLib.idle_add(self.update_main_statusbar, msg1 + ": " + msg2)"""

    def do_clone_wrapper(self):
        try:
            self.do_clone()
        except Exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            return self.ui_manager.completed_operation(
                callable_fn=self.completed_clone,
                succeeded=False,
                message=_("Error restoring image: ") + tb,
            )

    def do_clone(self):
        self.requested_stop = False
        # Clear proc dictionary
        self.proc.clear()
        self.summary_message_lock = threading.Lock()
        self.summary_message = ""
        if self.is_rescue:
            with self.summary_message_lock:
                self.summary_message += _("Rescue option is enabled.") + "\n"

        if isinstance(self.image, QemuImage):
            is_associated, failed_message = self.image.associate_nbd(
                QEMU_NBD_NBD_DEVICE
            )
            if not is_associated:
                return self.ui_manager.completed_operation(
                    callable_fn=self.completed_clone,
                    succeeded=False,
                    message="Failed to associate QemuImage: " + failed_message,
                )
        if not (
            isinstance(self.image, QemuImage)
            or isinstance(self.image, MetadataOnlyImage)
        ):
            # This shouldn't ever happen
            return self.ui_manager.completed_operation(
                callable_fn=self.completed_clone,
                succeeded=False,
                message="Unsupported image",
            )
        # self, selected_drive_key, partitions_to_backup, drive_state, dest_dir, backup_notes,
        #                      compression_dict, completed_backup_callback, on_separate_thread=True
        #
        # clone_destination_drive, clone_mapping_dict, is_overwriting_partition_table,
        #                       completed_callback

        partitions_to_backup = self.image.get_partitions_to_backup(
            self.clone_mapping_dict.keys()
        )
        is_success, message = self.backup_manager.start_backup(
            selected_drive_key=self.image.long_device_node,
            partitions_to_backup=partitions_to_backup,
            drive_state=self.system_drive_state,
            dest_dir=self.temp_dir,
            backup_notes="",
            compression_dict={"format": "uncompressed", "level": None},
            is_rescue=self.is_rescue,
            completed_backup_callback=CloneManager._ignore_suboperation_callback,
            metadata_only_image_to_annotate=self.image,
            on_separate_thread=False,
        )

        if not is_success:
            # During a clone operation, the user will only care about Backup Manager if it failed.
            with self.summary_message_lock and self.backup_manager.summary_message_lock:
                self.summary_message += self.backup_manager.summary_message + "\n"
            self.ui_manager.display_error_message(summary_message=message)
            return self.ui_manager.completed_operation(
                callable_fn=self.completed_clone, succeeded=False, message=message
            )

        self.image.scan_dummy_images_and_annotate(self.temp_dir)

        # image, restore_destination_drive, restore_mapping_dict, is_overwriting_partition_table,
        #                       completed_callback, on_separate_thread=True
        is_success, message = self.restore_manager.start_restore(
            image=self.image,
            restore_destination_drive=self.clone_destination_drive,
            restore_mapping_dict=self.clone_mapping_dict,
            is_overwriting_partition_table=self.is_overwriting_partition_table,
            is_rescue=self.is_rescue,
            completed_callback=CloneManager._ignore_suboperation_callback,
            on_separate_thread=False,
        )
        with self.summary_message_lock and self.restore_manager.summary_message_lock:
            self.summary_message += self.restore_manager.summary_message + "\n"
        if not is_success:
            self.ui_manager.display_error_message(summary_message=message)
            return self.ui_manager.completed_operation(
                callable_fn=self.completed_clone, succeeded=False, message=message
            )
        else:
            return self.ui_manager.completed_operation(
                callable_fn=self.completed_clone, succeeded=True, message=""
            )

    # Expected to run on GTK event thread
    def completed_clone(self, succeeded, message):
        clone_timeend = datetime.now()
        duration_minutes = Utility.get_human_readable_minutes_seconds(
            (clone_timeend - self.clone_timestart).total_seconds()
        )

        if isinstance(self.image, QemuImage):
            is_success, failed_message = self.image.deassociate_nbd(QEMU_NBD_NBD_DEVICE)
            if not is_success:
                with self.summary_message_lock:
                    self.summary_message += message + "\n"
                self.ui_manager.display_error_message(summary_message=failed_message)
                print(failed_message)

        if succeeded:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        else:
            # Keep temp_dir for debugging
            print("Not deleting " + self.temp_dir)
        self.ui_manager.remove_all_main_statusbar(context_id="restore")
        self.ui_manager.remove_all_main_statusbar(context_id="clone")
        with self.clone_in_progress_lock:
            self.clone_in_progress = False
        if succeeded:
            print("Success")
        else:
            with self.summary_message_lock:
                self.summary_message += message + "\n"
            self.ui_manager.display_error_message(summary_message=message)
            print("Failure")
        with self.summary_message_lock:
            self.summary_message += (
                "\n"
                + _("Operation took {num_minutes} minutes.").format(
                    num_minutes=duration_minutes
                )
                + "\n"
            )
            post_task_action: str = self.ui_manager.get_post_task_action()
            if post_task_action != "DO_NOTHING":
                if succeeded:
                    has_scheduled, msg = Utility.schedule_shutdown_reboot(
                        post_task_action
                    )
                    self.summary_message += "\n" + msg
                else:
                    self.summary_message += "\n" + _(
                        "Shutdown/Reboot cancelled due to errors."
                    )
        is_unmounted, umount_message = Utility.umount_warn_on_busy(
            "/mnt/backup", is_lazy_umount=True
        )
        if not is_unmounted:
            print(umount_message)
            with self.summary_message_lock:
                self.summary_message += umount_message + "\n"
        self.populate_summary_page()
        self.completed_callback(succeeded)

    def populate_summary_page(self):
        with self.summary_message_lock:
            summary_message = self.summary_message
        print("Populating summary pages with:\n\n" + summary_message)
        text_to_display = """<b>{heading}</b>

{message}"""
        if isinstance(self.image, QemuImage):
            # For QemuImage instances, update the "Restore" mode UI widgets rather than the "Clone" mode UI widgets.
            heading = _("Restore Summary")
        else:
            heading = _("Clone Summary")
        text_to_display = text_to_display.format(
            heading=_(heading),
            message=self.ui_manager.escape_text(input=self.summary_message),
        )
        self.ui_manager.display_summary_text(text_to_display=text_to_display)

    # CloneManager handles the threading so calls to the BackupManager/RestoreManager are done synchronously, so the
    # callback is not required here.
    @staticmethod
    def _ignore_suboperation_callback(is_success):
        print(
            "CloneManager ignoring scheduled callback (using return code for directly called function)"
        )
