# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
#   Copyright (C) 2003-2020 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2019-2020 Rescuezilla.com <rescuezilla@gmail.com>
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

import gi

from mount_backup_image_partition import MountBackupImagePartition
from wizard_state import IMAGE_EXPLORER_DIR

gi.require_version("Gtk", "3.0")

from parser.clonezilla_image import ClonezillaImage
from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import ErrorMessageModalPopup, Utility, _


# Signals should automatically propagate to processes called with subprocess.run().

class ImageExplorerManager:
    def __init__(self, builder, image_explorer_partition_selection_list,
                 set_support_information_linkbutton_visible, set_patreon_call_to_action_visible):
        self.image_explorer_in_progress = False
        self.is_partition_mounted = False
        self.builder = builder
        self.main_statusbar = self.builder.get_object("main_statusbar")
        self.image_explorer_partition_selection_list = image_explorer_partition_selection_list
        self.restore_partition_treeview = self.builder.get_object("restore_step4_image_partition_treeview")
        # FIXME: Remove need to passing the support info / patreon visibility functions for improved abstraction
        self.set_support_information_linkbutton_visible = set_support_information_linkbutton_visible
        self.set_patreon_call_to_action_visible = set_patreon_call_to_action_visible
        # proc dictionary
        self.proc = collections.OrderedDict()
        self.requested_stop = False

    def is_image_explorer_in_progress(self):
        return self.image_explorer_in_progress

    def cancel_image_explorer(self):
        return

    # Intended to be called via event thread
    def update_main_statusbar(self, message):
        context_id = self.main_statusbar.get_context_id("image_explorer")
        self.main_statusbar.push(context_id, message)

    # Based on the PartitionsToRestore function
    def populate_partition_selection_table(self, selected_image):
        self.image_explorer_partition_selection_list.clear()
        self.builder.get_object("button_mount").set_sensitive(False)

        self.selected_image = selected_image
        if isinstance(self.selected_image, ClonezillaImage):
            for image_format_dict_key in self.selected_image.image_format_dict_dict.keys():
                print("ClonezillaImage contains partition " + image_format_dict_key)
                # TODO: Support Clonezilla multidisk
                short_device_key = self.selected_image.short_device_node_disk_list[0]
                if self.selected_image.does_image_key_belong_to_device(image_format_dict_key, short_device_key):
                    if self.selected_image.image_format_dict_dict[image_format_dict_key]['is_lvm_logical_volume']:
                        human_friendly_partition_name = image_format_dict_key
                        flat_description = "Logical Volume " + image_format_dict_key + ": " + self.selected_image.flatten_partition_string(
                            short_device_key, image_format_dict_key)
                    else:
                        image_base_device_node, image_partition_number = Utility.split_device_string(image_format_dict_key)
                        human_friendly_partition_name = "#" + str(image_partition_number) + " (" + image_format_dict_key + ")"
                        flat_description = str(image_partition_number) + ": " + self.selected_image.flatten_partition_string(
                            short_device_key, image_format_dict_key)
                    self.image_explorer_partition_selection_list.append([image_format_dict_key, human_friendly_partition_name, flat_description])
        elif isinstance(self.selected_image, RedoBackupLegacyImage):
            for short_device_node in self.selected_image.short_device_node_partition_list:
                image_base_device_node, image_partition_number = Utility.split_device_string(short_device_node)
                human_friendly_partition_name = "#" + str(image_partition_number) + " (" + short_device_node + ")"
                flat_description = str(image_partition_number) + ": " + self.selected_image.flatten_partition_string(short_device_node)
                self.image_explorer_partition_selection_list.append([short_device_node, human_friendly_partition_name, flat_description])

    # Sets sensitivity of all elements on the Image Explorer page
    def set_parts_of_image_explorer_page_sensitive(self, is_sensitive):
        self.builder.get_object("image_explorer_image_partition_treeview").set_sensitive(is_sensitive)
        self.builder.get_object("button_back").set_sensitive(is_sensitive)
        self.builder.get_object("button_next").set_sensitive(is_sensitive)

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
            self.set_support_information_linkbutton_visible(True)
            self.set_patreon_call_to_action_visible(False)
        else:
            self.set_mounted_state(False)
            self.set_support_information_linkbutton_visible(False)
            self.set_patreon_call_to_action_visible(True)

    def _post_backup_image_mount_callback(self, is_success, error_message=""):
        if not is_success:
            error = ErrorMessageModalPopup(self.builder, error_message)
            self.set_support_information_linkbutton_visible(True)
            self.set_patreon_call_to_action_visible(False)
        else:
            self.set_mounted_state(True)
            self.set_support_information_linkbutton_visible(False)
            self.set_patreon_call_to_action_visible(True)

    def mount_partition(self, selected_partition_key):
        if self.is_partition_mounted:
            # Unmount partition
            MountBackupImagePartition.unmount(self.builder, callback=self._post_backup_image_unmount_callback,
                                              mounted_path=IMAGE_EXPLORER_DIR)
        else:
            MountBackupImagePartition.mount_backup_image_partition(self.builder,
                                                                   callback=self._post_backup_image_mount_callback,
                                                                   backup_image=self.selected_image,
                                                                   partition_key_to_mount=selected_partition_key,
                                                                   destination_path=IMAGE_EXPLORER_DIR)

    def _on_image_partition_mount_completed_callback(self, is_success):
        if is_success:
            self.set_support_information_linkbutton_visible(False)
            self.set_patreon_call_to_action_visible(True)
            self.set_parts_of_image_explorer_page_sensitive(False)
        else:
            self.set_support_information_linkbutton_visible(True)
            self.set_patreon_call_to_action_visible(False)
            self.set_parts_of_image_explorer_page_sensitive(True)