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
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------

import gi

from parser.clonezilla_image import ClonezillaImage
from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import Utility

gi.require_version("Gtk", "3.0")


class ImageManager:
    def __init__(self, builder, image_explorer_partition_selection_list):
        self.builder = builder
        self.image_explorer_partition_selection_list = image_explorer_partition_selection_list
        self.restore_partition_treeview = self.builder.get_object("restore_step4_image_partition_treeview")
        self.win = self.builder.get_object("main_window")

    # Based on the PartitionsToRestore function
    def populate_partition_selection_table(self, selected_image):
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



        """
    def initialize_image_explorer_partition_list(self, selected_image, dest_drive_node, dest_drive_desc,
                                                 dest_drive_dict):
        self.selected_image = selected_image
        self.dest_drive_node = dest_drive_node
        self.dest_drive_desc = dest_drive_desc
        self.dest_drive_dict = dest_drive_dict

        if isinstance(self.selected_image, ClonezillaImage):
            print("Got selected Clonezilla image: " + str(selected_image.image_format_dict_dict))
        elif isinstance(self.selected_image, RedoBackupLegacyImage):
            print("Got selected RedoBackupLegacy image: " + str(selected_image.sfdisk_dict))
        self._use_image_partition_table()

        info_string = "<b>" + _("Selected image") + "</b> " + GObject.markup_escape_text(
            self.selected_image.absolute_path) + "\n" + "<b>" + _(
            "Destination device") + "</b> " + GObject.markup_escape_text(self.dest_drive_desc)
        if isinstance(self.selected_image, ClonezillaImage) and len(
                self.selected_image.short_device_node_disk_list) > 1:
            # FIXME: Support Clonezilla multidisk images with subdisk selection combobox
            info_string += "\n" + "<b>" + _(
                "IMPORTANT: Only selecting FIRST disk in Clonezilla image containing MULTIPLE DISKS.") + "</b>"
        self.builder.get_object("restore_step4_selected_image_text").set_markup(info_string)

        print("Have selected image " + str(self.selected_image))
        print("Have drive dict " + str(self.dest_drive_dict))

        # If the image has a partition table, the overwrite toggle is enabled and defaults to True. Otherwise
        # it's not possible to overwrite the partition table.
        overwrite_partition_table_checkbutton = self.builder.get_object("overwrite_partition_table_checkbutton")
        overwrite_partition_table_checkbutton.set_sensitive(self.selected_image.has_partition_table())
        overwrite_partition_table_checkbutton.set_active(self.selected_image.has_partition_table())"""
