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
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------
import collections
import os
import subprocess
import threading
import traceback
from datetime import datetime

import gi

from backup_manager import BackupManager
from image_explorer_manager import ImageExplorerManager
from mount_local_path import MountLocalPath
from mount_network_path import MountNetworkPath
from restore_manager import RestoreManager
from verify_manager import VerifyManager

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

from partitions_to_restore import PartitionsToRestore
from drive_query import DriveQuery
from image_folder_query import ImageFolderQuery
from parser.sfdisk import Sfdisk
from utility import ErrorMessageModalPopup, BrowseSelectionPopup, Utility, AreYouSureModalPopup, _
from wizard_state import Mode, Page, MOUNT_DIR, IMAGE_EXPLORER_DIR, NETWORK_UI_WIDGET_MODES


class Handler:
    """As an event driven application, this handler is where most of the application logic is done.
   The widgets in the GTKBuilder (.glade) XML file are configured with the function names defined in this file (eg,
   when a button is clicked).

   Thread-safety note: All functions (other than the constructor) are expected to be called via the GTK event loop.
   Do long-running operations in a separate Python thread and update the UI by queueing a function to run on the GTK
   event loop up using GLib.idle_add(). Please note, these Python threads created by the threading module are subject
   to the CPython GIL (Global Interpreter Lock) which can be leveraged for some limited threadsafety guarantees.
   If/when the GIL is leveraged for the threadsafety guarantees, this will be clearly commented.

   Documentation/API reference:
   For developers with some knowledge of other UI frameworks but less experience with Python/PyGTK specifically, here is
   a gentle reference/tutorial with good examples: https://python-gtk-3-tutorial.readthedocs.io/en/latest/
   Generic GTK3 API documentation https://developer.gnome.org/gtk3/stable/
   PyGTK-specific API documentation https://developer.gnome.org/pygtk/stable/class-gtknotebook.html
   """

    def __init__(self, builder):
        # The GTKBuilder is used to retrieve any arbitrary GTK widgets using "id" attributes in the GTKBuilder
        # (.glade) XML file
        self.builder = builder
        self.save_partition_list_store = self.builder.get_object("save_partition_list")
        self.drive_list_store = self.builder.get_object("drive_list")
        self.mount_partition_list_store = self.builder.get_object("mount_partition_list")
        self.image_list_store = self.builder.get_object("image_list")

        self.has_prior_summary_page = False
        self.memory_bus_width = Utility.get_memory_bus_width().strip()
        self.version = Utility.read_file_into_string("/usr/share/rescuezilla/VERSION").strip()
        self.commit_date = Utility.read_file_into_string("/usr/share/rescuezilla/GIT_COMMIT_DATE").strip()
        self.main_statusbar = self.builder.get_object("main_statusbar")
        self.human_readable_version = self.version + " (" + self.memory_bus_width + ") " + self.commit_date
        self.mode = Mode.BACKUP
        self.current_page = Page.WELCOME
        self.drive_query = DriveQuery(self.builder, self.drive_list_store, self.save_partition_list_store,
                                      self.mount_partition_list_store)
        self.image_folder_query = ImageFolderQuery(self.builder, self.image_list_store)

        self.restore_partition_selection_list = self.builder.get_object("restore_partition_selection_list")
        self.backup_image = PartitionsToRestore(self.builder, self.restore_partition_selection_list)
        self.image_explorer_partition_selection_list = self.builder.get_object("image_explorer_partition_selection_list")
        self.set_support_information_linkbutton_visible(False)
        self.set_patreon_call_to_action_visible(True)
        # TODO: Remove the need to set this variable to None
        self.selected_drive_key = None
        # Ensuring toggle button is ticked and consistency of the user-interface elements that are associated with this
        # checkbox.

        # Initialize perform action option
        self.post_operation_action_list = self.builder.get_object("post_operation_action_list")
        self.post_operation_action_list.append(["DO_NOTHING", _("Do nothing")])
        self.post_operation_action_list.append(["SHUTDOWN", _("Shutdown")])
        self.post_operation_action_list.append(["REBOOT", _("Reboot")])

        # Initialize compression tool option
        self.compression_tool_list = self.builder.get_object("compression_tool_list")
        self.compression_tool_list.append(["gzip", _("gzip") + " " + _("(default)")])
        self.compression_tool_list.append(["zstd", _("zstandard")])
        self.compression_tool_list.append(["uncompressed", _("Uncompressed (Suitable for use with Image Explorer)")])
        compression_format_combobox = self.builder.get_object("backup_step6_compression_format_combobox")
        compression_format_combobox.set_active(0)
        self.compression_tool_changed(compression_format_combobox)

        self.backup_manager = BackupManager(builder, self.human_readable_version)
        self.restore_manager = RestoreManager(builder)
        self.verify_manager = VerifyManager(builder)
        # FIXME: Remove need to passing the support info / patreon visibility functions for improved abstraction
        self.image_explorer_manager = ImageExplorerManager(builder, self.image_explorer_partition_selection_list,
                                                           self.set_support_information_linkbutton_visible, self.set_patreon_call_to_action_visible)

        # Add network protocols combobox model
        self.network_share_protocol_list = self.builder.get_object("network_share_protocol_list")
        self.network_share_protocol_list.append(["SMB", _("Windows shared folder (SMB/CIFS, Samba)")])
        # No need to translate "SSH" strings (unless the description string is expanded upon)
        self.network_share_protocol_list.append(["SSH", "SSH"])
        self.network_share_protocol_list.append(["NFS", "NFS"])
        # Manage all network protocol UI widgets
        self.network_protocol_widget_dict = {
            'network_protocol_combobox': {},
            'frame_local': {},
            'frame_network': {},
            'network_use_local_radiobutton': {},
            'network_server_label': {},
            'network_server': {},
            'network_username_label': {},
            'network_username': {},
            'network_remote_path_label': {},
            'network_remote_path': {},
            'network_password_label': {},
            'network_password': {},
            'network_domain_label': {},
            'network_domain': {},
            'network_version_label': {},
            'network_version': {},
            'network_ssh_idfile': {},
            'network_ssh_idfile_box': {},
            'network_ssh_idfile_label': {},
        }
        for mode in NETWORK_UI_WIDGET_MODES:
            for prefix in self.network_protocol_widget_dict.keys():
                id = mode.name.lower() + "_" + prefix
                object = self.builder.get_object(id)
                if object is None:
                    raise ValueError("Could not find: " + id)
                self.network_protocol_widget_dict[prefix][mode] = object

        self.mount_partition_selection_treeselection_id_dict = {
            Mode.BACKUP: "backup_mount_partition_selection_treeselection",
            Mode.RESTORE: "restore_mount_partition_selection_treeselection",
            Mode.VERIFY: "verify_mount_partition_selection_treeselection",
            Mode.IMAGE_EXPLORER: "image_explorer_mount_partition_selection_treeselection"}

        self.larger_to_smaller_details_msg = _("The source partition table's final partition ({source}: {source_size} bytes) must refer to a region completely within the destination disk ({destination_size} bytes).")
        self.larger_to_smaller_info_msg = _("Rescuezilla cannot yet automatically shrink partitions to restore from large disks to smaller disks. The final partition currently must always completely reside within the destination disk.\n\nCurrently the only way to restore to disks smaller than original is to first use GParted Partition Editor to shrink the final partition of the original disk before making a new backup image. Please read the following instructions for more information:\n\n{url}").format(url="https://github.com/rescuezilla/rescuezilla/wiki/HOWTO:-Restoring-to-a-smaller-disk.-Eg,-1000GB-HDD-to-500GB-SSD")

        self.requested_shutdown_lock = threading.Lock()
        self.requested_shutdown = False
        self.display_welcome_page()

    # Suggest the user read the frequently asked questions, then potentially proceed to the support forum.
    def set_support_information_linkbutton_visible(self, is_visible):
        self.builder.get_object("welcome_support_linkbutton").set_visible(is_visible)
        self.builder.get_object("backup_step9_support_linkbutton").set_visible(is_visible)
        self.builder.get_object("restore_step7_support_linkbutton").set_visible(is_visible)
        self.builder.get_object("verify_step4_support_linkbutton").set_visible(is_visible)
        self.builder.get_object("image_explorer_step3_support_linkbutton").set_visible(is_visible)

    # Ask users to contribute on the crowdfunding website Patreon.
    def set_patreon_call_to_action_visible(self, is_visible):
        self.builder.get_object("welcome_patreon_linkbutton").set_visible(is_visible)
        self.builder.get_object("backup_step9_patreon_linkbutton").set_visible(is_visible)
        self.builder.get_object("restore_step7_patreon_linkbutton").set_visible(is_visible)
        self.builder.get_object("verify_step4_patreon_linkbutton").set_visible(is_visible)
        self.builder.get_object("image_explorer_step3_patreon_linkbutton").set_visible(is_visible)

    def display_welcome_page(self):
        self.current_page = Page.WELCOME

        self.main_statusbar.push(self.main_statusbar.get_context_id("version"), self.human_readable_version)

        self.builder.get_object("mode_tabs").set_current_page(0)
        # Disable the forward/previous navigation buttons on the welcome page
        self.builder.get_object("button_next").set_sensitive(False)
        if self.has_prior_summary_page:
            self.builder.get_object("button_back").set_sensitive(True)
        else:
            self.builder.get_object("button_back").set_sensitive(False)

        # TODO: Find more efficient way to do this
        combobox_list = []
        # Re-initialize the image selection network protocol
        for mode in NETWORK_UI_WIDGET_MODES:
            self.network_protocol_widget_dict['network_use_local_radiobutton'][mode].set_active(True)
            combobox_list.append(self.network_protocol_widget_dict['network_protocol_combobox'][mode])
        # Reset all comboboxes
        for combobox in combobox_list:
            combobox.set_active(0)
            combobox.set_active_iter(combobox.get_active_iter())
            self.network_protocol_combobox_changed(combobox)

        # Post action comboboxes don't have signal handlers so no need to trigger anything
        self.builder.get_object("backup_step7_perform_action_combobox").set_active(0)
        self.builder.get_object("restore_step5_perform_action_combobox").set_active(0)

    def display_backup_wizard(self, button):
        self.mode = Mode.BACKUP
        self.drive_query.start_query(self._display_error_message_callback)
        self.main_statusbar.pop(self.main_statusbar.get_context_id("version"))
        self.current_page = Page.BACKUP_SOURCE_DRIVE_SELECTION
        self.builder.get_object("mode_tabs").set_current_page(1)
        self.builder.get_object("backup_tabs").set_current_page(0)
        # Re-enable the forward/previous navigation buttons
        self.builder.get_object("button_back").set_sensitive(True)
        self.builder.get_object("button_next").set_sensitive(True)
        # Remove access to any summary pages from prior operations
        self.has_prior_summary_page = False

    def display_restore_wizard(self, button):
        self.mode = Mode.RESTORE
        self.drive_query.start_query(self._display_error_message_callback)
        self.main_statusbar.pop(self.main_statusbar.get_context_id("version"))
        self.current_page = Page.RESTORE_SOURCE_LOCATION_SELECTION
        self.builder.get_object("mode_tabs").set_current_page(2)
        self.builder.get_object("restore_tabs").set_current_page(0)
        # Re-enable the forward/previous navigation buttons
        self.builder.get_object("button_back").set_sensitive(True)
        self.builder.get_object("button_next").set_sensitive(True)
        # Remove access to any summary pages from prior operations
        self.has_prior_summary_page = False

    def display_verify_wizard(self, button):
        self.mode = Mode.VERIFY
        self.drive_query.start_query(self._display_error_message_callback)
        self.main_statusbar.pop(self.main_statusbar.get_context_id("version"))
        self.current_page = Page.VERIFY_SOURCE_LOCATION_SELECTION
        self.builder.get_object("mode_tabs").set_current_page(3)
        self.builder.get_object("verify_tabs").set_current_page(0)
        # Re-enable the forward/previous navigation buttons
        self.builder.get_object("button_back").set_sensitive(True)
        self.builder.get_object("button_next").set_sensitive(True)
        # Remove access to any summary pages from prior operations
        self.has_prior_summary_page = False

    def display_image_explorer_wizard(self, button):
        self.mode = Mode.IMAGE_EXPLORER
        self.drive_query.start_query(self._display_error_message_callback)
        self.main_statusbar.pop(self.main_statusbar.get_context_id("version"))
        self.builder.get_object("mode_tabs").set_current_page(4)
        self.builder.get_object("image_explorer_tabs").set_current_page(0)
        self.current_page = Page.IMAGE_EXPLORER_SOURCE_LOCATION_SELECTION
        # Re-enable the forward/previous navigation buttons
        self.builder.get_object("button_back").set_sensitive(True)
        self.builder.get_object("button_next").set_sensitive(True)
        # Remove access to any summary pages from prior operations
        self.has_prior_summary_page = False
        self.builder.get_object("button_mount").set_sensitive(False)
        self.builder.get_object("button_open_file_manager").set_sensitive(False)
        self.image_explorer_manager.set_parts_of_image_explorer_page_sensitive(True)
        self.is_partition_mounted = False

    def _display_error_message_callback(self, is_success, message):
        if not is_success:
            error = ErrorMessageModalPopup(self.builder, message)
            self.display_welcome_page()

    def get_row(self, id):
        treeselection = self.builder.get_object(id)
        list_store, tree_path_list = treeselection.get_selected_rows()
        if len(list_store) == 0 or len(tree_path_list) == 0:
            return list_store, None
        iter = list_store.get_iter(tree_path_list[0])
        return list_store, iter

    def next_tab(self, button):
        try:
            print("Currently mode=" + str(self.mode) + " on page " + str(self.current_page))
            if self.mode == Mode.BACKUP:
                if self.current_page == Page.BACKUP_SOURCE_DRIVE_SELECTION:
                    list_store, iter = self.get_row("backup_drive_selection_treeselection")
                    if iter is None:
                        error = ErrorMessageModalPopup(self.builder, "No source drive selected. Please select source "
                                                                     "drive to backup")
                    else:
                        # Get first column (which is hidden/invisible) containing the drive shortdevname (eg, 'sda')
                        self.selected_drive_key = list_store.get(iter, 0)[0]
                        print("User selected drive: " + self.selected_drive_key)
                        self.drive_query.populate_partition_selection_table(self.selected_drive_key)

                        self.selected_drive_enduser_friendly_drive_number = list_store.get(iter, 1)[0]
                        self.selected_drive_capacity = list_store.get(iter, 2)[0]
                        # FIXME: May be None for devices like /dev/md127
                        self.selected_drive_model = list_store.get(iter, 3)[0]

                        self.current_page = Page.BACKUP_SOURCE_PARTITION_SELECTION
                        self.builder.get_object("backup_tabs").set_current_page(1)
                elif self.current_page == Page.BACKUP_SOURCE_PARTITION_SELECTION:
                    partition_list_store = self.builder.get_object("save_partition_list")
                    if 'partitions' not in self.drive_query.drive_state[self.selected_drive_key].keys():
                        error = ErrorMessageModalPopup(self.builder,
                                                       "Backup of drives without a partition table not yet supported by current version of Rescuezilla.\nSupport for this will be added in a future version.\n\nHowever, as a temporary workaround, it is possible to use Clonezilla's 'savedisk' option to backup the drive, and then use Rescuezilla to restore that image.")
                        return
                    self.partitions_to_backup = collections.OrderedDict()
                    has_atleast_one = False
                    for row in partition_list_store:
                        print("row is " + str(row))
                        if row[1]:
                            self.partitions_to_backup[row[0]] = self.drive_query.drive_state[self.selected_drive_key]['partitions'][row[0]]
                            self.partitions_to_backup[row[0]]['description'] = row[2]
                            has_atleast_one = True
                    if not has_atleast_one:
                        error = ErrorMessageModalPopup(self.builder, "Nothing selected!")
                    else:
                        self.drive_query.populate_mount_partition_table(ignore_drive_key=self.selected_drive_key)
                        self.current_page = Page.BACKUP_DESTINATION_LOCATION_SELECTION
                        self.builder.get_object("backup_tabs").set_current_page(2)
                elif self.current_page == Page.BACKUP_DESTINATION_LOCATION_SELECTION:
                    selected_partition_key, self.destination_partition_description = self.handle_mount_local_or_remote()
                elif self.current_page == Page.BACKUP_DESTINATION_FOLDER:
                    enduser_date = datetime.today().strftime('%Y-%m-%d-%H%M') + "-img-rescuezilla"
                    self.builder.get_object("backup_name").set_text(enduser_date)
                    self.current_page = Page.BACKUP_IMAGE_NAME_SELECTION
                    self.builder.get_object("backup_tabs").set_current_page(4)
                elif self.current_page == Page.BACKUP_IMAGE_NAME_SELECTION:
                    selected_directory = self.builder.get_object("backup_folder_label").get_text()
                    folder_name = self.builder.get_object("backup_name").get_text()
                    self.dest_dir = os.path.join(selected_directory, folder_name)
                    self.backup_notes = self.builder.get_object("backup_notes").get_text()
                    print ("going to write to" + str(self.dest_dir))
                    self.current_page = Page.BACKUP_COMPRESSION_CUSTOMIZATION
                    self.builder.get_object("backup_tabs").set_current_page(5)
                elif self.current_page == Page.BACKUP_COMPRESSION_CUSTOMIZATION:
                    self.compression_dict = self.get_compression_dict()
                    self.confirm_backup_configuration()
                    self.current_page = Page.BACKUP_CONFIRM_CONFIGURATION
                    self.builder.get_object("backup_tabs").set_current_page(6)
                elif self.current_page == Page.BACKUP_CONFIRM_CONFIGURATION:
                    self.current_page = Page.BACKUP_PROGRESS
                    self.builder.get_object("backup_tabs").set_current_page(7)
                    self.post_task_action = Utility.get_combobox_key(self.builder.get_object("backup_step7_perform_action_combobox"))
                    self.backup_manager.start_backup(self.selected_drive_key, self.partitions_to_backup, self.drive_query.drive_state, self.dest_dir, self.backup_notes, self.compression_dict, self.post_task_action, self._on_operation_completed_callback)
                    # Disable back/next button until the restore completes
                    self.builder.get_object("button_next").set_sensitive(False)
                    self.builder.get_object("button_back").set_sensitive(False)
                    # On success, display the Patreon call-to-action.
                    self.set_patreon_call_to_action_visible(True)
                    # Disable back/next button until the backup completes
                    self.builder.get_object("button_back").set_sensitive(False)
                    # self.builder.get_object("button_next").set_sensitive(False)
                elif self.current_page == Page.BACKUP_PROGRESS:
                    self.current_page = Page.BACKUP_SUMMARY_SCREEN
                    self.builder.get_object("backup_tabs").set_current_page(8)
                    self.builder.get_object("button_next").set_sensitive(True)
                    self.builder.get_object("button_back").set_sensitive(False)
                elif self.current_page == Page.BACKUP_SUMMARY_SCREEN:
                    self.has_prior_summary_page = True
                    self.display_welcome_page()
                else:
                    print("Unexpected page " + str(self.current_page))
            elif self.mode == Mode.RESTORE:
                if self.current_page == Page.RESTORE_SOURCE_LOCATION_SELECTION:
                    self.image_source_partition_key, description = self.handle_mount_local_or_remote()
                elif self.current_page == Page.RESTORE_SOURCE_IMAGE_SELECTION:

                    list_store, iter = self.get_row("restore_image_selection_treeselection")
                    if iter is None:
                        error = ErrorMessageModalPopup(self.builder, "No image selected")
                    else:
                        self.selected_image_absolute_path = list_store.get(iter, 0)[0]
                        print("User image: " + self.selected_image_absolute_path)
                        image = self.image_folder_query.image_dict[self.selected_image_absolute_path]
                        if image.is_needs_decryption:
                            error = ErrorMessageModalPopup(self.builder,
                                                           "Ecryptfs encrypted images are not supported by current version of Rescuezilla.\n\nSupport for ecryptfs will be improved in a future version.\n\nHowever, as a temporary workaround, it is possible to carefully use the mount command line utility to decrypt the image, and then point Rescuezilla to this ecryptfs mount point and then use Rescuezilla to restore the image as normal.")
                        elif image.image_format == "QEMU_FORMAT":
                            error = ErrorMessageModalPopup(self.builder,
                                                           "Virtual Machine images and raw disk images can be mounted and explored by the current version of Rescuezilla, but not restored.\n\nSupport for restoring such images will be added in a future version.")
                        else:
                            self.current_page = Page.RESTORE_DESTINATION_DRIVE_SELECTION
                            self.builder.get_object("restore_tabs").set_current_page(2)
                elif self.current_page == Page.RESTORE_DESTINATION_DRIVE_SELECTION:
                    list_store, iter = self.get_row("restore_step3_drive_selection_treeselection")
                    if iter is None:
                        error = ErrorMessageModalPopup(self.builder, "Please select destination drive to mount")
                    else:
                        self.restore_destination_drive = list_store.get(iter, 0)[0]
                        if self.image_source_partition_key is not None and self.image_source_partition_key.startswith(self.restore_destination_drive):
                            # TODO: Handle this situation more effectively than "startswith" on the device nodes.
                            error = ErrorMessageModalPopup(self.builder, "Destination device cannot be the same as source image device.")
                            return
                        # Set a nice description like "sdc: 8.00 GB (TOSHIBA USB DRV)
                        self.restore_destination_drive_desc = list_store.get(iter, 1)[0] + ": " + list_store.get(iter, 2)[0]
                        drive_model = list_store.get(iter, 3)[0]
                        if drive_model is not None:
                            # Some devices, such as RAID devices /dev/md127 don't set the drive model field.
                            self.restore_destination_drive_desc += " (" + drive_model + ")"
                        print("User selected destination drive: " + self.restore_destination_drive)
                        self.selected_image = self.image_folder_query.image_dict[self.selected_image_absolute_path]
                        drive_dict = self.drive_query.drive_state[self.restore_destination_drive]
                        # TODO: Compare self.selected_image.size_bytes to drive_dict["capacity"] in bytes
                        try:
                            self.backup_image.initialize_individual_partition_restore_list(self.selected_image,
                                                                                           self.restore_destination_drive,
                                                                                           self.restore_destination_drive_desc,
                                                                                           drive_dict)
                        except Exception as e:
                            tb = traceback.format_exc()
                            traceback.print_exc()
                            error = ErrorMessageModalPopup(self.builder, "Unable to process image " + tb)
                        self.current_page = Page.RESTORE_DESTINATION_PARTITION_SELECTION
                        self.builder.get_object("restore_tabs").set_current_page(3)
                elif self.current_page == Page.RESTORE_DESTINATION_PARTITION_SELECTION:
                    self.is_overwriting_partition_table = self.builder.get_object(
                        "overwrite_partition_table_checkbutton").get_active()
                    restore_partition_selection_list = self.builder.get_object("restore_partition_selection_list")
                    self.partitions_to_restore = collections.OrderedDict()
                    has_atleast_one = False
                    for row in restore_partition_selection_list:
                        print("row is " + str(row))
                        if row[1]:
                            image_key = row[0]
                            self.partitions_to_restore[image_key] = {
                                "description": row[2],
                                "dest_key": row[3],
                                "dest_description": row[4]
                            }
                            print("Added " + image_key + " " + str(self.partitions_to_restore[image_key]))
                            has_atleast_one = True
                    if not has_atleast_one:
                        error = ErrorMessageModalPopup(self.builder, "Please select partitions to restore!")
                    else:
                        last_image_partition_key, last_image_partition_final_byte = Sfdisk.get_highest_offset_partition(self.selected_image.normalized_sfdisk_dict)
                        destination_capacity_bytes = self.drive_query.drive_state[self.restore_destination_drive][
                            'capacity']
                        # Rough check if restoring to a smaller disk. Note: For GPT disks the secondary GPT backup
                        # should mean the final partition should be a few bytes smaller than the capacity on GPT disks
                        if self.is_overwriting_partition_table and last_image_partition_final_byte > destination_capacity_bytes:
                            details = self.larger_to_smaller_details_msg.format(source=last_image_partition_key, source_size=last_image_partition_final_byte, destination_size=destination_capacity_bytes)
                            error = ErrorMessageModalPopup(self.builder, details + "\n\n" + self.larger_to_smaller_info_msg)
                        else:
                            self.confirm_restore_configuration()
                            self.current_page = Page.RESTORE_CONFIRM_CONFIGURATION
                            self.builder.get_object("restore_tabs").set_current_page(4)
                elif self.current_page == Page.RESTORE_CONFIRM_CONFIGURATION:
                    # Disable back/next button until the restore completes
                    self.builder.get_object("button_next").set_sensitive(False)
                    self.builder.get_object("button_back").set_sensitive(False)
                    self.post_task_action = Utility.get_combobox_key(self.builder.get_object("restore_step5_perform_action_combobox"))
                    AreYouSureModalPopup(self.builder,
                                         _("Are you sure you want to restore the backup to {destination_drive}? Doing so will permanently overwrite data on this drive!").format(destination_drive = self.restore_destination_drive),
                                         self._restore_confirmation_callback)
                elif self.current_page == Page.RESTORE_PROGRESS:
                    self.current_page = Page.RESTORE_SUMMARY_SCREEN
                    self.builder.get_object("restore_tabs").set_current_page(6)
                    self.builder.get_object("button_back").set_sensitive(False)
                    self.builder.get_object("button_next").set_sensitive(True)
                elif self.current_page == Page.RESTORE_SUMMARY_SCREEN:
                    self.has_prior_summary_page = True
                    self.display_welcome_page()
                else:
                    print("Unexpected page " + str(self.current_page))
            elif self.mode == Mode.VERIFY:
                if self.current_page == Page.VERIFY_SOURCE_LOCATION_SELECTION:
                    image_source_partition_key, description = self.handle_mount_local_or_remote()
                elif self.current_page == Page.VERIFY_SOURCE_IMAGE_SELECTION:
                    list_store, iter = self.get_row("verify_image_selection_treeselection")
                    if iter is None:
                        error = ErrorMessageModalPopup(self.builder, "No image selected")
                    else:
                        self.selected_image_absolute_path = list_store.get(iter, 0)[0]
                        print("User image: " + self.selected_image_absolute_path)
                        image = self.image_folder_query.image_dict[self.selected_image_absolute_path]
                        if image.is_needs_decryption:
                            error = ErrorMessageModalPopup(self.builder,
                                                           "Ecryptfs encrypted images are not supported by current version of Rescuezilla.\n\nSupport for ecryptfs will be improved in a future version.\n\nHowever, as a temporary workaround, it is possible to carefully use the mount command line utility to decrypt the image, and then point Rescuezilla to this ecryptfs mount point and then use Rescuezilla to restore the image as normal.")
                        else:
                            self.current_page = Page.VERIFY_PROGRESS
                            self.builder.get_object("verify_tabs").set_current_page(2)
                            self.builder.get_object("button_back").set_sensitive(False)
                            self.builder.get_object("button_next").set_sensitive(False)
                            self.verify_manager.start_verify(image, self._on_operation_completed_callback)
                elif self.current_page == Page.VERIFY_PROGRESS:
                    self.current_page = Page.VERIFY_SUMMARY_SCREEN
                    self.builder.get_object("verify_tabs").set_current_page(3)
                    self.builder.get_object("button_back").set_sensitive(True)
                    self.builder.get_object("button_next").set_sensitive(True)
                elif self.current_page == Page.VERIFY_SUMMARY_SCREEN:
                    self.has_prior_summary_page = True
                    self.display_welcome_page()
                else:
                    print("Unexpected page " + str(self.current_page))
            elif self.mode == Mode.IMAGE_EXPLORER:
                if self.current_page == Page.IMAGE_EXPLORER_SOURCE_LOCATION_SELECTION:
                    image_source_partition_key, description = self.handle_mount_local_or_remote()
                elif self.current_page == Page.IMAGE_EXPLORER_SOURCE_IMAGE_SELECTION:
                    list_store, iter = self.get_row("image_explorer_image_selection_treeselection")
                    if iter is None:
                        error = ErrorMessageModalPopup(self.builder, "No image selected")
                    else:
                        self.selected_image_absolute_path = list_store.get(iter, 0)[0]
                        print("User image: " + self.selected_image_absolute_path)
                        image = self.image_folder_query.image_dict[self.selected_image_absolute_path]
                        if image.image_format == "FSARCHIVER_FORMAT":
                            error = ErrorMessageModalPopup(self.builder,
                                                           "FSArchiver images cannot be mounted with Image Explorer with the current version of Rescuezilla. But FSArchiver images CAN be restored with the current version of Rescuezilla.\n\nSupport for exploring FSArchiver images may be added in a future version.")
                        elif image.is_needs_decryption:
                            error = ErrorMessageModalPopup(self.builder,
                                                           "Ecryptfs encrypted images are not supported by current version of Rescuezilla.\n\nSupport for ecryptfs will be improved in a future version.\n\nHowever, as a temporary workaround, it is possible to carefully use the mount command line utility to decrypt the image, and then point Rescuezilla to this ecryptfs mount point and then use Rescuezilla to access the image as normal.")
                        else:
                            self.current_page = Page.IMAGE_EXPLORER_PARTITION_MOUNT
                            self.builder.get_object("image_explorer_tabs").set_current_page(2)
                            # Temporarily disable the next button until the user has successfully mounted a partition.
                            # This indicate pressing 'Next' is NOT the way to mount the partition.
                            self.builder.get_object("button_next").set_sensitive(False)
                            try:
                                self.image_explorer_manager.populate_partition_selection_table(image)
                            except Exception as e:
                                tb = traceback.format_exc()
                                traceback.print_exc()
                                error = ErrorMessageModalPopup(self.builder, "Unable to process image " + tb)
                elif self.current_page == Page.IMAGE_EXPLORER_PARTITION_MOUNT:
                    self.has_prior_summary_page = True
                    self.display_welcome_page()
                else:
                    print("Unexpected page " + str(self.current_page))
            else:
                print("Unexpected mode " + str(self.mode))
            print(" Moving to mode=" + str(self.mode) + " on page " + str(self.current_page))
        except Exception as e:
            tb = traceback.format_exc()
            traceback.print_exc()
            error = ErrorMessageModalPopup(self.builder, tb)

    def prev_tab(self, button):
        try:
            print("Currently mode=" + str(self.mode) + " on page " + str(self.current_page))
            if self.mode == Mode.BACKUP:
                if self.current_page == Page.WELCOME:
                    print("Previous backup summary page")
                    self.builder.get_object("mode_tabs").set_current_page(1)
                    self.builder.get_object("backup_tabs").set_current_page(7)
                    self.current_page = Page.BACKUP_SUMMARY_SCREEN
                    self.builder.get_object("button_back").set_sensitive(False)
                    self.builder.get_object("button_next").set_sensitive(True)
                elif self.current_page == Page.BACKUP_SOURCE_DRIVE_SELECTION:
                    self.current_page = Page.WELCOME
                    self.display_welcome_page()
                elif self.current_page == Page.BACKUP_SOURCE_PARTITION_SELECTION:
                    self.current_page = Page.BACKUP_SOURCE_DRIVE_SELECTION
                    self.builder.get_object("backup_tabs").set_current_page(0)
                elif self.current_page == Page.BACKUP_DESTINATION_LOCATION_SELECTION:
                    self.current_page = Page.BACKUP_SOURCE_PARTITION_SELECTION
                    self.builder.get_object("backup_tabs").set_current_page(1)
                elif self.current_page == Page.BACKUP_DESTINATION_FOLDER:
                    self.current_page = Page.BACKUP_DESTINATION_LOCATION_SELECTION
                    self.builder.get_object("backup_tabs").set_current_page(2)
                elif self.current_page == Page.BACKUP_IMAGE_NAME_SELECTION:
                    self.current_page = Page.BACKUP_DESTINATION_FOLDER
                    self.builder.get_object("backup_tabs").set_current_page(3)
                elif self.current_page == Page.BACKUP_COMPRESSION_CUSTOMIZATION:
                    self.current_page = Page.BACKUP_IMAGE_NAME_SELECTION
                    self.builder.get_object("backup_tabs").set_current_page(4)
                elif self.current_page == Page.BACKUP_CONFIRM_CONFIGURATION:
                    self.current_page = Page.BACKUP_COMPRESSION_CUSTOMIZATION
                    self.builder.get_object("backup_tabs").set_current_page(5)
                elif self.current_page == Page.BACKUP_PROGRESS:
                    self.current_page = Page.BACKUP_CONFIRM_CONFIGURATION
                    self.builder.get_object("backup_tabs").set_current_page(6)
                elif self.current_page == Page.BACKUP_SUMMARY_SCREEN:
                    self.current_page = Page.BACKUP_PROGRESS
                    self.builder.get_object("backup_tabs").set_current_page(7)
                else:
                    print("Unexpected page " + str(self.current_page))
            elif self.mode == Mode.RESTORE:
                if self.current_page == Page.WELCOME:
                    print("Previous restore summary page")
                    self.builder.get_object("mode_tabs").set_current_page(2)
                    self.builder.get_object("restore_tabs").set_current_page(6)
                    self.current_page = Page.RESTORE_SUMMARY_SCREEN
                    self.builder.get_object("button_back").set_sensitive(False)
                    self.builder.get_object("button_next").set_sensitive(True)
                elif self.current_page == Page.RESTORE_SOURCE_LOCATION_SELECTION:
                    self.current_page = Page.WELCOME
                    self.display_welcome_page()
                elif self.current_page == Page.BACKUP_SOURCE_PARTITION_SELECTION:
                    self.builder.get_object("mode_tabs").set_current_page(0)
                elif self.current_page == Page.RESTORE_SOURCE_IMAGE_SELECTION:
                    self.current_page = Page.RESTORE_SOURCE_LOCATION_SELECTION
                    self.builder.get_object("restore_tabs").set_current_page(0)
                elif self.current_page == Page.RESTORE_DESTINATION_DRIVE_SELECTION:
                    self.current_page = Page.RESTORE_SOURCE_IMAGE_SELECTION
                    self.builder.get_object("restore_tabs").set_current_page(1)
                elif self.current_page == Page.RESTORE_DESTINATION_PARTITION_SELECTION:
                    self.current_page = Page.RESTORE_DESTINATION_DRIVE_SELECTION
                    self.builder.get_object("restore_tabs").set_current_page(2)
                elif self.current_page == Page.RESTORE_CONFIRM_CONFIGURATION:
                    self.current_page = Page.RESTORE_DESTINATION_PARTITION_SELECTION
                    self.builder.get_object("restore_tabs").set_current_page(3)
                elif self.current_page == Page.RESTORE_PROGRESS:
                    self.current_page = Page.RESTORE_CONFIRM_CONFIGURATION
                    self.builder.get_object("restore_tabs").set_current_page(4)
                elif self.current_page == Page.RESTORE_SUMMARY_SCREEN:
                    self.current_page = Page.RESTORE_PROGRESS
                    self.builder.get_object("restore_tabs").set_current_page(5)
                else:
                    print("Unexpected page " + str(self.current_page))
            elif self.mode == Mode.VERIFY:
                if self.current_page == Page.WELCOME:
                    print("Previous verify summary page")
                    self.builder.get_object("mode_tabs").set_current_page(3)
                    self.current_page = Page.VERIFY_SUMMARY_SCREEN
                    self.builder.get_object("verify_tabs").set_current_page(3)
                    self.builder.get_object("button_back").set_sensitive(True)
                    self.builder.get_object("button_next").set_sensitive(True)
                elif self.current_page == Page.VERIFY_SOURCE_LOCATION_SELECTION:
                    self.current_page = Page.WELCOME
                    self.display_welcome_page()
                elif self.current_page == Page.VERIFY_SOURCE_IMAGE_SELECTION:
                    self.current_page = Page.VERIFY_SOURCE_LOCATION_SELECTION
                    self.builder.get_object("verify_tabs").set_current_page(0)
                elif self.current_page == Page.VERIFY_PROGRESS:
                    self.current_page = Page.VERIFY_SOURCE_IMAGE_SELECTION
                    self.builder.get_object("verify_tabs").set_current_page(1)
                elif self.current_page == Page.VERIFY_SUMMARY_SCREEN:
                    self.current_page = Page.VERIFY_SOURCE_IMAGE_SELECTION
                    self.builder.get_object("verify_tabs").set_current_page(1)
                else:
                    print("Unexpected page " + str(self.current_page))
            elif self.mode == Mode.IMAGE_EXPLORER:
                if self.current_page == Page.WELCOME:
                    print("Previous image explorer summary page")
                    self.builder.get_object("mode_tabs").set_current_page(4)
                    self.current_page = Page.IMAGE_EXPLORER_PARTITION_MOUNT
                    self.builder.get_object("image_explorer_tabs").set_current_page(2)
                    self.builder.get_object("button_back").set_sensitive(True)
                    self.builder.get_object("button_next").set_sensitive(True)
                elif self.current_page == Page.IMAGE_EXPLORER_SOURCE_LOCATION_SELECTION:
                    self.current_page = Page.WELCOME
                    self.display_welcome_page()
                elif self.current_page == Page.IMAGE_EXPLORER_SOURCE_IMAGE_SELECTION:
                    self.current_page = Page.IMAGE_EXPLORER_SOURCE_LOCATION_SELECTION
                    self.builder.get_object("image_explorer_tabs").set_current_page(0)
                elif self.current_page == Page.IMAGE_EXPLORER_PARTITION_MOUNT:
                    self.current_page = Page.IMAGE_EXPLORER_SOURCE_IMAGE_SELECTION
                    self.builder.get_object("image_explorer_tabs").set_current_page(1)
                else:
                    print("Unexpected page " + str(self.current_page))
            else:
                print("Unexpected mode " + str(self.mode))
            print("Moving to mode=" + str(self.mode) + " on page " + str(self.current_page))
        except Exception as e:
            tb = traceback.format_exc()
            traceback.print_exc()
            error = ErrorMessageModalPopup(self.builder, tb)

    def _post_mount_callback(self, is_success, error_message, mounted_path=None):
        if not is_success or mounted_path is None:
                error = ErrorMessageModalPopup(self.builder, error_message)
        else:
            if self.mode == Mode.BACKUP:
                self.current_page = Page.BACKUP_DESTINATION_FOLDER
                self.builder.get_object("backup_tabs").set_current_page(3)
                self.selected_image_folder(mounted_path, False)
            elif self.mode == Mode.RESTORE:
                self.current_page = Page.RESTORE_SOURCE_IMAGE_SELECTION
                self.builder.get_object("restore_tabs").set_current_page(1)
                self.selected_image_folder(mounted_path, True)
            elif self.mode == Mode.VERIFY:
                self.current_page = Page.VERIFY_SOURCE_IMAGE_SELECTION
                self.builder.get_object("verify_tabs").set_current_page(1)
                self.selected_image_folder(mounted_path, True)
            elif self.mode == Mode.IMAGE_EXPLORER:
                self.current_page = Page.IMAGE_EXPLORER_SOURCE_IMAGE_SELECTION
                self.builder.get_object("image_explorer_tabs").set_current_page(1)
                self.selected_image_folder(mounted_path, True)

    # Called via AreYouSure prompt
    def _restore_confirmation_callback(self, is_affirmative):
        if is_affirmative:
            self.current_page = Page.RESTORE_PROGRESS
            self.builder.get_object("restore_tabs").set_current_page(5)
            self.restore_manager.start_restore(self.selected_image, self.restore_destination_drive,
                                               self.partitions_to_restore, self.is_overwriting_partition_table,
                                               self.post_task_action,
                                               self._on_operation_completed_callback)
            # Display the Patreon call-to-action.
            self.set_patreon_call_to_action_visible(True)
        else:
            self.builder.get_object("button_back").set_sensitive(True)
            self.builder.get_object("button_next").set_sensitive(True)

    def _on_operation_completed_callback(self, is_success):
        if is_success:
            self.set_support_information_linkbutton_visible(False)
            self.set_patreon_call_to_action_visible(True)
        else:
            self.set_support_information_linkbutton_visible(True)
            self.set_patreon_call_to_action_visible(False)
        self.next_tab(None)

    def row_activated_next_tab(self, treeview, path, view_column):
        # Callback for double click (row-activate).
        self.next_tab(None)
        # Not using index = path.get_indices()[0], as the next button could also be used not double-click.

    def save_partition_toggled(self, cellrendertoggle, path):
        print("Backup partition toggled: " + str(path))
        iter = self.save_partition_list_store.get_iter(path)
        # Get the first column
        state = self.save_partition_list_store.get(iter, 1)[0]
        # invert toggle
        self.save_partition_list_store.set_value(iter, 1, not state)

    # Callback for double click (row-activate) on backup mode partitions to backup toggle
    # TODO: Directly call save_partition_toggled from above, to reduce duplication
    def row_activated_backup_partition_toggle(self, treeview, path, view_column):
        list_store, iter = self.get_row("backup_partitions_treeselection")
        state = list_store.get(iter, 1)[0]
        list_store.set_value(iter, 1, not state)

    def exit_app(self):
        print("Exiting Rescuezilla.")
        try:
            # Launch subprocess to unmount target directory. Subprocess is detached so it doesn't block Rescuezilla's
            # shutdown.
            subprocess.Popen(["umount", MOUNT_DIR])
        except Exception as e:
            tb = traceback.format_exc()
            traceback.print_exc()
        Gtk.main_quit()

    def _cancel_current_operations(self, is_affirmative):
        if is_affirmative:
            with self.requested_shutdown_lock:
                self.requested_shutdown = True
            print("Cancelling current operations.")
            if self.image_folder_query.is_image_folder_query_in_progress():
                self.image_folder_query.cancel_image_folder_query()
            if self.restore_manager.is_restore_in_progress():
                self.restore_manager.cancel_restore()
            if self.backup_manager.is_backup_in_progress():
                self.backup_manager.cancel_backup()
            if self.verify_manager.is_verify_in_progress():
                self.verify_manager.cancel_verify()
            if self.image_explorer_manager.is_image_explorer_in_progress():
                self.image_explorer_manager.cancel_image_explorer()

    # Main window receives close signal
    def main_window_delete_event(self, widget, event):
        print("Received Rescuezilla shutdown request")
        has_already_requested_shutdown = False
        with self.requested_shutdown_lock:
            has_already_requested_shutdown = self.requested_shutdown

        if not has_already_requested_shutdown and (self.backup_manager.is_backup_in_progress() or self.restore_manager.is_restore_in_progress()):
            print("An operation is in progress. Do you wish to cancel?")
            AreYouSureModalPopup(self.builder, _("An operation is in progress. Do you wish to cancel?"),
                                 self._cancel_current_operations)
        else:
            self.exit_app()
        # Return True to prevent the window closing from this signal, and instead rely on the dialog box callback.
        # ("True to stop other handlers from being invoked for the event. False to propagate the event further.")
        return True

    def restore_file_changed(self):
        print("test")

    def network_protocol_combobox_changed(self, combobox):
        # Shows and hides certain fields depending on the protocol.
        # Shows different label text depending on the protocol (eg, "Remote path" for SSH and "Exported path" for NFS).
        # Also whether or not a  field is depends on the network protocol.
        optional = " (" + _("Optional") + "):"
        network_protocol_key = Utility.get_combobox_key(combobox)
        if network_protocol_key == "SMB":
            for mode in NETWORK_UI_WIDGET_MODES:
                self.network_protocol_widget_dict['network_server_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_server_label'][mode].set_text(_("Share location (UNC path)") + ": ")
                self.network_protocol_widget_dict['network_server'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_username_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_username_label'][mode].set_text(_("Username"))
                self.network_protocol_widget_dict['network_username'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_remote_path_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_remote_path'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_password_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_password_label'][mode].set_text(_("Password"))
                self.network_protocol_widget_dict['network_password'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_domain_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_domain_label'][mode].set_text(_("Domain"))
                self.network_protocol_widget_dict['network_domain'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_version_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_version_label'][mode].set_text(_("Version"))
                self.network_protocol_widget_dict['network_version'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_ssh_idfile_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_ssh_idfile_box'][mode].set_visible(False)
        elif network_protocol_key == "SSH":
            for mode in NETWORK_UI_WIDGET_MODES:
                self.network_protocol_widget_dict['network_server_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_server_label'][mode].set_text(_("Server") + ": ")
                self.network_protocol_widget_dict['network_server'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_username_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_username_label'][mode].set_text(_("Username") + ": ")
                self.network_protocol_widget_dict['network_username'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_remote_path_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_remote_path_label'][mode].set_text(_("Remote path"))
                self.network_protocol_widget_dict['network_remote_path'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_password_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_password_label'][mode].set_text(_("Password"))
                self.network_protocol_widget_dict['network_password'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_domain_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_domain'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_version_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_version'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_ssh_idfile_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_ssh_idfile_label'][mode].set_text(_("Identity File"))
                self.network_protocol_widget_dict['network_ssh_idfile_box'][mode].set_visible(True)
        elif network_protocol_key == "NFS":
            for mode in NETWORK_UI_WIDGET_MODES:
                self.network_protocol_widget_dict['network_server_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_server_label'][mode].set_text(_("Server") + ": ")
                self.network_protocol_widget_dict['network_server'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_username_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_username'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_remote_path_label'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_remote_path_label'][mode].set_text(_("Exported path") + ": ")
                self.network_protocol_widget_dict['network_remote_path'][mode].set_visible(True)
                self.network_protocol_widget_dict['network_password_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_password'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_domain_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_domain'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_version_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_version'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_ssh_idfile_label'][mode].set_visible(False)
                self.network_protocol_widget_dict['network_ssh_idfile_box'][mode].set_visible(False)

        else:
            raise ValueError("Unknown network protocol")
        return

    def select_ssh_idfile(self, button):
        BrowseSelectionPopup(self.builder, callback=self.selected_ssh_idfile,
                             default_directory="/", is_allow_selecting_folder_outside_mount = True, select_file = True)
        return

    def selected_ssh_idfile(self, text, is_allow_selecting_folder_outside_mount):
        print("Received SSH ID file path" + text)
        for mode in NETWORK_UI_WIDGET_MODES:
            self.network_protocol_widget_dict['network_ssh_idfile'][mode].set_text(text)

    def compression_tool_changed(self, combobox):
        compression_level_scale = self.builder.get_object("backup_step6_compression_level_scale")
        # "The step size is used when the user clicks the gtk.Scrollbar arrows or moves gtk.Scale via the arrow keys.
        # The page size is used for example when moving via Page Up or Page Down keys."
        compression_level_scale.set_increments(step=1, page=5)

        compression_level_box = self.builder.get_object("backup_step6_compression_level_selection_box")
        tree_iter = combobox.get_active_iter()
        range = (0,0)
        default_value = 0
        if tree_iter is not None:
            model = combobox.get_model()
            compression_key, = model[tree_iter][:1]
            if compression_key == "uncompressed":
                compression_level_box.set_visible(False)

            elif compression_key == "gzip":
                compression_level_box.set_visible(True)
                # Like gzip binary, the pigz multithreaded gzip arguments typically takes compression levels 1-9,
                # though pigz can actually take 0 (no compression) and 11 ("-11 gives a few percent better
                # compression at a severe cost in execution time").
                range = (0, 9)
                # Default compression for pigz is 6
                default_value = 6
            elif compression_key == "zstd":
                compression_level_box.set_visible(True)
                # As with zstd command-line utility, hiding high compression levels 20+ (maximum 22) by default as it
                # "a lot more memory. Note that decompression will also require more memory when using these levels"
                range = (1, 19)
                # Default compression for zstd is 3
                default_value = 3

        compression_level_scale.clear_marks()
        compression_level_scale.set_range(range[0], range[1])
        compression_level_scale.set_value(default_value)
        compression_level_scale.add_mark(range[0], Gtk.PositionType.TOP, _("Fastest"))
        compression_level_scale.add_mark(range[1], Gtk.PositionType.TOP, _("Best"))
        return

    def get_compression_dict(self):
        compression_dict = {}

        compression_level_combobox = self.builder.get_object("backup_step6_compression_format_combobox")
        tree_iter = compression_level_combobox.get_active_iter()
        compression_key = ""
        if tree_iter is not None:
            model = compression_level_combobox.get_model()
            compression_key, = model[tree_iter][:1]

        if compression_key == "":
            raise ValueError("Compression not specified")

        compression_level_scale = self.builder.get_object("backup_step6_compression_level_scale")
        level = int(compression_level_scale.get_value())

        compression_dict = {"format": compression_key, "level": level}

        return compression_dict

    # GtkToggleButton handler for switching the image location selection between local folder, and network share.
    def image_location_toggle(self, toggle_button):
        is_local_active = self.network_protocol_widget_dict['network_use_local_radiobutton'][self.mode].get_active()
        for mode in NETWORK_UI_WIDGET_MODES:
            self.network_protocol_widget_dict['frame_local'][mode].set_visible(is_local_active)
            self.network_protocol_widget_dict['frame_network'][mode].set_visible(not is_local_active)
        return

    def handle_mount_local_or_remote(self):
        selected_partition_key = None
        partition_description = None
        if self.network_protocol_widget_dict['network_use_local_radiobutton'][self.mode].get_active():
            list_store, iter = self.get_row(self.mount_partition_selection_treeselection_id_dict[self.mode])
            if iter is None:
                error = ErrorMessageModalPopup(self.builder, "Please select drive to mount")
            else:
                # Get first column (which is hidden/invisible) containing the drive shortdevname (eg, 'sda')
                selected_partition_key = list_store.get(iter, 0)[0]
                partition_description = list_store.get(iter, 3)[0]
                print("User selected partition: " + selected_partition_key)
                # Callback determines whether wizard proceeds
                MountLocalPath(self.builder, self._post_mount_callback, selected_partition_key,
                               MOUNT_DIR)
        else:
            partition_description = "network share"
            MountNetworkPath(self.builder, self._post_mount_callback, self.mode, self.network_protocol_widget_dict, MOUNT_DIR)
        return selected_partition_key, partition_description

    def restore_partition_toggled(self, cell_render_toggle, path):
        iter = self.restore_partition_selection_list.get_iter(path)
        new_state = not self.restore_partition_selection_list.get(iter, 1)[0]
        self.backup_image.toggle_restore_of_row(iter, new_state)

    # Callback for double click (row-activate) on restore partition mapping toggle
    # TODO: Directly call restore_partition_toggled from above, to reduce duplication
    def row_activated_restore_partition_toggle(self, treeview, path, view_column):
        list_store, iter = self.get_row("restore_step4_image_partition_treeview_treeselection")
        new_state = not list_store.get(iter, 1)[0]
        self.backup_image.toggle_restore_of_row(iter, new_state)

    def destination_partition_node_changed(self, cell_renderer_combo, path, cell_render_combo_iter):
        # Retrieve the selected string from the CellRendererCombo combo widget.
        cell_render_model = cell_renderer_combo.get_property("model")
        key = cell_render_model.get_value(cell_render_combo_iter, 0)
        enduser_friendly_string = cell_render_model.get_value(cell_render_combo_iter, 1)
        self.backup_image.change_combo_box(path, key, enduser_friendly_string)

    def overwrite_partition_table_toggle(self, toggle_button):
        self.backup_image.overwrite_partition_table_toggle(toggle_button.get_active())

    def show_hidden_devices_toggle(self, toggle_button):
        new_state = toggle_button.get_active()
        # Ensure all the similar toggle buttons in the application are consistent.
        # FIXME: Not ideal from an abstraction perspective
        self.builder.get_object("backup_step1_show_hidden_devices").set_active(new_state)
        self.builder.get_object("backup_step3_show_hidden_devices").set_active(new_state)
        self.builder.get_object("restore_step1_show_hidden_devices").set_active(new_state)
        self.builder.get_object("restore_step3_show_hidden_devices").set_active(new_state)
        self.drive_query.set_show_hidden_information(new_state)
        # Refresh the tables.
        # FIXME: Not ideal from an abstraction perspective
        if self.selected_drive_key is not None:
            self.drive_query.populate_partition_selection_table(self.selected_drive_key)
            self.drive_query.populate_mount_partition_table(ignore_drive_key=self.selected_drive_key)
        else:
            self.drive_query.populate_drive_selection_table()


    def open_url_as_non_root(self, button):
        Utility.open_url_as_non_root("ubuntu", button.get_uri())
        return

    def select_image_folder(self, button):
        folder_selection_popup = BrowseSelectionPopup(self.builder, callback=self.selected_image_folder, default_directory=MOUNT_DIR, is_allow_selecting_folder_outside_mount=True)
        return

    def select_image_explorer_image_folder(self, button):
        folder_selection_popup = BrowseSelectionPopup(self.builder, callback=self.selected_image_folder, default_directory="/", is_allow_selecting_folder_outside_mount=True)
        return

    def selected_image_folder(self, text, is_allow_selecting_folder_outside_mount):
        print("Received path " + text)
        if not is_allow_selecting_folder_outside_mount and not MOUNT_DIR in text:
            error = ErrorMessageModalPopup(self.builder,
                                           _("You must select a folder inside {location}").format(location=MOUNT_DIR) + "\n" + _("Please select a different folder."))
        else:
            self.image_folder_query.query_folder(text)

    def confirm_backup_configuration(self):
        number = GObject.markup_escape_text(self.selected_drive_enduser_friendly_drive_number)
        device = GObject.markup_escape_text(self.selected_drive_key)
        size = GObject.markup_escape_text(self.selected_drive_capacity)
        if self.selected_drive_model is None:
            model = ""
        else:
            model = GObject.markup_escape_text(self.selected_drive_model)
        description = GObject.markup_escape_text(self.destination_partition_description)
        partition_list_string = ""
        for key in self.partitions_to_backup.keys():
            partition_list_string += "    " + GObject.markup_escape_text(key) + ":  " + GObject.markup_escape_text(
                self.partitions_to_backup[key]['description']) + "\n"

        compression_string = "<b>" + _("Compression format: ") + "</b>" + self.compression_dict['format'] + ", " + _("Compression level: ") + str(self.compression_dict['level'])

        source_drive_heading = GObject.markup_escape_text(_("Source drive"))
        backup_partitions_heading = GObject.markup_escape_text(_("Backing up the following partition"))
        backup_image_destination_heading = GObject.markup_escape_text(_("The backup image will be written into folder {dest_dir} on {description}").format(dest_dir=self.dest_dir, description=description))

        text_to_display = f"""
<b>{source_drive_heading}</b> {number} [{size}] ({model})

<b>{backup_partitions_heading}</b>:
{partition_list_string}

{compression_string}

<b>{backup_image_destination_heading}</b>
"""
        self.builder.get_object("backup_step7_confirm_config_program_defined_text").set_markup(text_to_display)

    def confirm_restore_configuration(self):
        # number = GObject.markup_escape_text(self.selected_drive_enduser_friendly_drive_number)

        print("Partitions to restore is " + str(self.partitions_to_restore))
        source_image_absolute_path = self.selected_image_absolute_path
        destination_drive_description = self.restore_destination_drive_desc
        restore_partition_list_string = ""
        for key in self.partitions_to_restore.keys():
            image_part_description = GObject.markup_escape_text(self.partitions_to_restore[key]["description"])
            dest_key = GObject.markup_escape_text(self.partitions_to_restore[key]["dest_key"])
            dest_description = GObject.markup_escape_text(self.partitions_to_restore[key]["dest_description"])
            restore_partition_list_string += "    " + GObject.markup_escape_text(
                key) + " (" + image_part_description + ")  ---->  " + dest_key + " (" + dest_description + ")\n"
        restore_partition_list_string += "\n"

        if self.is_overwriting_partition_table:
            overwriting_partition_table_string = "<b>" + _("WILL BE OVERWRITING PARTITION TABLE") + "</b>"
        else:
            overwriting_partition_table_string = _("Will <b>NOT</b> be overwriting partition table")

        source_image_heading = _("Source image")
        destination_drive_msg = _("Destination drive")
        restoring_following_partition_msg = _("Restoring the following partitions")

        text_to_display = f"""
<b>{source_image_heading}</b> {source_image_absolute_path}
<b>{destination_drive_msg}</b> {destination_drive_description}

<b>{restoring_following_partition_msg}</b>:
{restore_partition_list_string}

{overwriting_partition_table_string}
"""
        self.builder.get_object("restore_step5_confirm_config_program_defined_text").set_markup(text_to_display)

    def find_network_share(self, button):
        # FIXME: Overhaul network share handling.
        error = ErrorMessageModalPopup(self.builder, "Search network function is disabled and will be re-introduced in the next version.\n\nPlease enter the network details manually.")

    def partition_selection_changed(self, treeselection):
        self.builder.get_object("button_mount").set_sensitive(True)

    def open_file_manager(self, button):
        Utility.open_path_in_filemanager_as_non_root("ubuntu", IMAGE_EXPLORER_DIR)

    # Callback for double click (row-activate).
    def row_activated_partition_selected(self, treeview, path, view_column):
        self.mount_partition(button=None)

    # Called via AreYouSure prompt
    def _mount_partition_confirmation_callback(self, is_affirmative):
        if is_affirmative:
            list_store, iter = self.get_row("image_explorer_image_partition_treeselection")
            selected_partition_key = list_store.get(iter, 0)[0]
            self.image_explorer_manager.mount_partition(selected_partition_key)

    def mount_partition(self, button):
        list_store, iter = self.get_row("image_explorer_image_partition_treeselection")
        selected_partition_key = list_store.get(iter, 0)[0]
        compression = self.image_explorer_manager.get_partition_compression(selected_partition_key)
        # Don't show reminder when unmounting or if the image is uncompressed.
        if not self.image_explorer_manager.get_mounted_state() and not compression == "uncompressed":
            AreYouSureModalPopup(self.builder,
                             _(
                                 "Reminder: Mounting large gzipped-compressed images WILL be UNUSABLY slow.\n\ngzip is the default compression format used by Clonezilla and Rescuezilla. If Rescuezilla doesn't cleanly unmount the image being explored a reboot may be required.\n\nIf you want a good experience with this BETA feature, it is highly recommeded you try an image WITHOUT COMPRESSION (created by Clonezilla's Expert Mode).\n\nAre you sure you want to continue?"),
                             self._mount_partition_confirmation_callback)
        else:
            # Unmounting doesn't need an AreYouSure popup.
            self._mount_partition_confirmation_callback(True)
