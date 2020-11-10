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
import os
import threading
import traceback
from os.path import join, isfile, isdir


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib

from parser.clonezilla_image import ClonezillaImage
from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import PleaseWaitModalPopup, ErrorMessageModalPopup, _
from wizard_state import MOUNT_DIR


class ImageFolderQuery:
    def __init__(self, builder, image_list_store):
        self.image_dict = {}
        # Relying on CPython GIL to communicate between threads.
        self.failed_to_read_image_dict = {}
        self.builder = builder
        self.image_list_store = image_list_store
        self.win = self.builder.get_object("main_window")
        self.icon_pixbufs = {
            "RESCUEZILLA_1.5_FORMAT": self.builder.get_object("rescuezilla_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                            GdkPixbuf.InterpType.BILINEAR),
            "REDOBACKUP_0.9.8_1.0.4_FORMAT": self.builder.get_object("redobackup_icon").get_pixbuf().scale_simple(32,
                                                                                                                  32,
                                                                                                                  GdkPixbuf.InterpType.BILINEAR),
            "CLONEZILLA_FORMAT": self.builder.get_object("clonezilla_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                      GdkPixbuf.InterpType.BILINEAR),
            "warning": self.builder.get_object("warning_icon").get_pixbuf().scale_simple(32, 32,
                                                                                         GdkPixbuf.InterpType.BILINEAR)
        }
        self.backup_label = self.builder.get_object("backup_folder_label")
        self.restore_label = self.builder.get_object("restore_folder_label")
        self.verify_label = self.builder.get_object("verify_folder_label")
        self.image_explorer_folder_label = self.builder.get_object("image_explorer_folder_label")
        self.query_path = MOUNT_DIR

    def query_folder(self, path):
        self.query_path = path
        self.image_list_store.clear()
        print("Starting scan of provided path " + self.query_path)
        self.backup_label.set_text(self.query_path)
        self.restore_label.set_text(self.query_path)
        self.verify_label.set_text(self.query_path)
        self.image_explorer_folder_label.set_text(self.query_path)
        self.image_list_store.clear()
        self.failed_to_read_image_dict.clear()
        self.win.set_sensitive(False)
        self.please_wait_popup = PleaseWaitModalPopup(self.builder, title=_("Please wait..."), message=_("Scanning folder for backup images..."))
        self.please_wait_popup.show()
        thread = threading.Thread(target=self.scan_image_directory)
        thread.daemon = True
        thread.start()

    def _populate_image_list_table(self):
        print("Populating image list table. Image dict is length: " + str(len(self.image_dict)))
        self.image_list_store.clear()
        traceback_messages = ""
        for key in self.image_dict.keys():
            try:
                image = self.image_dict[key]
                format = image.image_format
                if len(image.warning_dict.keys()) > 0:
                    warning_icon = self.icon_pixbufs['warning']
                else:
                    warning_icon = None

                self.image_list_store.append([key,
                                              format,
                                              warning_icon,
                                              self.icon_pixbufs[format],
                                              image.enduser_filename,
                                              image.enduser_readable_size,
                                              str(image.last_modified_timestamp),
                                              image.get_enduser_friendly_partition_description()
                                              ])
            except Exception as e:
                tb = traceback.format_exc()
                traceback_messages += tb + "\n\n"

        # Highlight first image if there is only 1 image.
        if len(self.image_dict.keys()) == 1:
            self.builder.get_object("restore_image_selection_treeselection").select_path(0)

        if len(self.failed_to_read_image_dict.keys()) > 0:
            for key in self.failed_to_read_image_dict.keys():
                traceback_messages += key + ": " + self.failed_to_read_image_dict[key] + "\n\n"

        if len(traceback_messages) > 0:
            ErrorMessageModalPopup(self.builder,
                                   _("Error processing the following images:") + "\n\n" + str(traceback_messages))
        self.please_wait_popup.destroy()

    def scan_file(self, absolute_path, filename, enduser_filename):
        print("Scan file " + absolute_path)
        try:
            image = None
            if isfile(absolute_path):
                # Identify Clonezilla images by presence of a file named "parts". Cannot use "clonezilla-img" or
                # "dev-fs.list" because these files were not created by in earlier Clonezilla versions. Cannot use
                # "disk" as Clonezilla's 'saveparts' function does not create it. But both 'savedisk' and 'saveparts'
                # always creates a file named 'parts' across every version of Clonezilla tested.
                if absolute_path.endswith("parts"):
                    print("Found Clonezilla image " + filename)
                    image = ClonezillaImage(absolute_path, enduser_filename)
                    image_warning_message = ""
                    for short_partition_key in image.warning_dict.keys():
                        image_warning_message += "    " + short_partition_key + ": " + image.warning_dict[short_partition_key] + "\n"
                    if len(image_warning_message) > 0:
                        self.failed_to_read_image_dict[
                            enduser_filename] = _("Unable to fully process the image associated with the following partitions:") + "\n" + image_warning_message + _("This can happen when loading images which Clonezilla was unable to completely backup. Any other filesystems within the image should be restorable as normal.")
                elif absolute_path.endswith(".backup"):
                    print("Found a Rescuezilla image " + filename)
                    # It is a Rescuezilla v1.0.5 or Redo Backup and Recovery
                    image = RedoBackupLegacyImage(absolute_path, enduser_filename, filename)
                    if len(image.warning_dict.keys()) > 0:
                        self.failed_to_read_image_dict[absolute_path] = _("Unable to fully process the following image:") + "\n" + image.warning_dict[image.absolute_path]
            if image is not None:
                self.image_dict[image.absolute_path] = image
        except Exception as e:
            print("Failed to read: " + absolute_path)
            tb = traceback.format_exc()
            self.failed_to_read_image_dict[enduser_filename] = tb
            traceback.print_exc()

    def scan_image_directory(self):
        self.image_dict.clear()
        self.failed_to_read_image_dict.clear()
        try:
            # list files and directories
            for filename in os.listdir(self.query_path):
                abs_base_scan_path = os.path.abspath(join(self.query_path, filename))
                print("Scanning " + abs_base_scan_path)
                if isfile(abs_base_scan_path):
                    print("Scanning file " + abs_base_scan_path)
                    self.scan_file(abs_base_scan_path, filename, filename)
                elif isdir(abs_base_scan_path):
                    # List the subdirectory (1 level deep)
                    for subdir_filename in os.listdir(abs_base_scan_path):
                        absolute_path = join(abs_base_scan_path, subdir_filename)
                        enduser_filename = os.path.join(filename, subdir_filename)
                        if isfile(absolute_path):
                            print("Scanning subdir file " + absolute_path)
                            self.scan_file(absolute_path, subdir_filename, enduser_filename)
        except Exception as e:
            tb = traceback.format_exc()
            GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                          "Failed to scan for images: " + tb)
        # Relying on CPython GIL to access the self.image_list
        GLib.idle_add(self._populate_image_list_table)
