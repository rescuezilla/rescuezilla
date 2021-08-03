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
import os
import threading
import traceback
from os.path import join, isfile, isdir


import gi

from parser.apart_gtk_image import ApartGtkImage
from parser.fogproject_image import FogProjectImage
from parser.foxclone_image import FoxcloneImage
from parser.fsarchiver_image import FsArchiverImage
from parser.redorescue_image import RedoRescueImage
from parser.qemu_image import QemuImage

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib

from parser.clonezilla_image import ClonezillaImage
from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import PleaseWaitModalPopup, ErrorMessageModalPopup, _
from wizard_state import MOUNT_DIR


class ImageFolderQuery:
    def __init__(self, builder, image_list_store):
        self.image_dict = {}
        self.ignore_folder_set = set()
        # Relying on CPython GIL to communicate between threads.
        self.failed_to_read_image_dict = {}
        self.builder = builder
        self.image_list_store = image_list_store
        self.win = self.builder.get_object("main_window")
        self.icon_pixbufs = {
            "RESCUEZILLA_1.0.5_FORMAT": self.builder.get_object("rescuezilla_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                            GdkPixbuf.InterpType.BILINEAR),
            "REDOBACKUP_0.9.2_FORMAT": self.builder.get_object("redobackup_v092_icon").get_pixbuf().scale_simple(32,
                                                                                                                  32,
                                                                                                                  GdkPixbuf.InterpType.BILINEAR),
            "REDOBACKUP_0.9.3_1.0.4_FORMAT": self.builder.get_object("redobackup_v093_to_v104_icon").get_pixbuf().scale_simple(32,
                                                                                                                  32,
                                                                                                                  GdkPixbuf.InterpType.BILINEAR),
            "CLONEZILLA_FORMAT": self.builder.get_object("clonezilla_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                      GdkPixbuf.InterpType.BILINEAR),
            "QEMU_FORMAT": self.builder.get_object("qemu_nbd_placeholder_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                      GdkPixbuf.InterpType.BILINEAR),
            "FOGPROJECT_FORMAT": self.builder.get_object("fogproject_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                      GdkPixbuf.InterpType.BILINEAR),
            "REDORESCUE_FORMAT": self.builder.get_object("redorescue_placeholder_icon").get_pixbuf().scale_simple(32,
                                                                                                                  32,
                                                                                                                  GdkPixbuf.InterpType.BILINEAR),
            "FOXCLONE_FORMAT": self.builder.get_object("foxclone_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                  GdkPixbuf.InterpType.BILINEAR),
            "FSARCHIVER_FORMAT": self.builder.get_object("fsarchiver_placeholder_icon").get_pixbuf().scale_simple(32, 32,
                                                                                                          GdkPixbuf.InterpType.BILINEAR),
            "APART_GTK_FORMAT": self.builder.get_object("apart_gtk_icon").get_pixbuf().scale_simple(32,
                                                                                                                  32,
                                                                                                                  GdkPixbuf.InterpType.BILINEAR),
            "warning": self.builder.get_object("warning_icon").get_pixbuf().scale_simple(32, 32,
                                                                                         GdkPixbuf.InterpType.BILINEAR),
            "padlock": self.builder.get_object("padlock_icon").get_pixbuf().scale_simple(32, 32,
                                                                                         GdkPixbuf.InterpType.BILINEAR)
        }
        self.backup_label = self.builder.get_object("backup_folder_label")
        self.restore_label = self.builder.get_object("restore_folder_label")
        self.verify_label = self.builder.get_object("verify_folder_label")
        self.image_explorer_folder_label = self.builder.get_object("image_explorer_folder_label")
        self.query_path = MOUNT_DIR
        self.requested_stop_lock = threading.Lock()
        self.requested_stop = False
        self.image_folder_query_in_progress = False

    def is_stop_requested(self):
        with self.requested_stop_lock:
            return self.requested_stop

    def is_image_folder_query_in_progress(self):
        return self.image_folder_query_in_progress

    def cancel_image_folder_query(self):
        with self.requested_stop_lock:
            self.requested_stop = True
        return

    def query_folder(self, path):
        with self.requested_stop_lock:
            self.requested_stop = False
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
        self.please_wait_popup = PleaseWaitModalPopup(self.builder, title=_("Please wait..."), message=_("Scanning folder for backup images...") + "\n\n" + _("Close this popup to cancel scanning the selected folder and subfolders."), on_close_callback=self.cancel_image_folder_query)
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

                if image.is_needs_decryption:
                    lock_icon = self.icon_pixbufs['padlock']
                else:
                    lock_icon = None
                self.image_list_store.append([key,
                                              format,
                                              warning_icon,
                                              lock_icon,
                                              self.icon_pixbufs[format],
                                              image.enduser_filename,
                                              image.enduser_readable_size,
                                              str(image.last_modified_timestamp),
                                              image.user_notes,
                                              image.get_enduser_friendly_partition_description()
                                              ])
            except Exception as e:
                tb = traceback.format_exc()
                traceback_messages += image.enduser_filename + ":\n" + tb + "\n\n"

        # Highlight first image if there is only 1 image.
        if len(self.image_dict.keys()) == 1:
            self.builder.get_object("restore_image_selection_treeselection").select_path(0)

        if len(self.failed_to_read_image_dict.keys()) > 0:
            for key in self.failed_to_read_image_dict.keys():
                traceback_messages += key + ": " + self.failed_to_read_image_dict[key] + "\n\n"

        if len(traceback_messages) > 0:
            ErrorMessageModalPopup(self.builder,str(traceback_messages), error_heading=_("Error processing the following images:"))
        self.please_wait_popup.destroy()

    def scan_file(self, absolute_path, enduser_filename):
        print("Scan file " + absolute_path)
        is_image = False
        try:
            temp_image_dict = {}
            dirname = os.path.dirname(absolute_path)
            if isfile(absolute_path) and dirname not in self.ignore_folder_set:
                head, filename = os.path.split(absolute_path)
                # Identify Clonezilla images by presence of a file named "parts". Cannot use "clonezilla-img" or
                # "dev-fs.list" because these files were not created by in earlier Clonezilla versions. Cannot use
                # "disk" as Clonezilla's 'saveparts' function does not create it. But both 'savedisk' and 'saveparts'
                # always creates a file named 'parts' across every version of Clonezilla tested.
                error_suffix = ""
                # Ignore [/mnt/backup/]/bin/parts and [/mnt/backup/]/sbin/parts
                if filename == "parts" and not filename == "bin" and not filename == "sbin":
                    print("Found Clonezilla image " + filename)
                    GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                  _("Scanning: {filename}").format(filename=absolute_path))
                    temp_image_dict = ClonezillaImage.get_clonezilla_image_dict(absolute_path, enduser_filename)
                    error_suffix = _(
                        "This can happen when loading images which Clonezilla was unable to completely backup.")
                    error_suffix += " " + _("Any other filesystems within the image should be restorable as normal.")
                    # Only 1 Clonezilla image per folder, so consider the image scanned
                    is_image = True
                elif absolute_path.endswith(".backup"):
                    # The legacy Redo Backup and Recovery v0.9.3-v1.0.4 format was adapted and extended Foxclone, so
                    # care is taken here to delineate the image formats by a simple heuristic: the existence of Foxclone's MBR backup.
                    foxclone_mbr = absolute_path.split(".backup")[0] + ".grub"
                    if os.path.exists(foxclone_mbr):
                        print("Found a Foxclone image " + filename)
                        GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                      _("Scanning: {filename}").format(filename=absolute_path))
                        temp_image_dict = {absolute_path: FoxcloneImage(absolute_path, enduser_filename, filename)}
                        error_suffix = _("Any other filesystems within the image should be restorable as normal.")
                        is_image = True
                    else:
                        print("Found a legacy Redo Backup / Rescuezilla v1.0.5 image " + filename)
                        GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                      _("Scanning: {filename}").format(filename=absolute_path))
                        temp_image_dict = {absolute_path: RedoBackupLegacyImage(absolute_path, enduser_filename, filename)}
                        error_suffix = _("Any other filesystems within the image should be restorable as normal.")
                        is_image = True
                elif absolute_path.endswith(".redo"):
                    # The Redo Rescue format's metadata is a JSON file ending in .redo. Unfortunately this conflicts
                    # with the legacy Redo Backup and Recovery 0.9.2 format, which also uses a metadata file ending in
                    # .redo, so care is taken here to delineate the image formats by a simple heuristic: whether or not
                    # the file is valid JSON.
                    if RedoRescueImage.is_valid_json(absolute_path):
                        # ".redo" is used for Redo Rescue format and Redo Backup and Recovery 0.9.2 format
                        print("Found Redo Rescue image " + filename)
                        GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                      _("Scanning: {filename}").format(filename=absolute_path))
                        temp_image_dict = {absolute_path: RedoRescueImage(absolute_path, enduser_filename, filename)}
                        error_suffix = _("Any other filesystems within the image should be restorable as normal.")
                        is_image = True
                    else:
                        print("Found a legacy Redo Backup and Recovery v0.9.2 image " + filename)
                        GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                      _("Scanning: {filename}").format(filename=absolute_path))
                        temp_image_dict = {absolute_path: RedoBackupLegacyImage(absolute_path, enduser_filename, filename)}
                        error_suffix = _("Any other filesystems within the image should be restorable as normal.")
                        is_image = True
                elif absolute_path.endswith(".partitions") and not absolute_path.endswith(".minimum.partitions"):
                    print("Found FOG Project image " + filename)
                    GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                  _("Scanning: {filename}").format(filename=absolute_path))
                    temp_image_dict = {absolute_path: FogProjectImage(absolute_path, enduser_filename, filename)}
                    error_suffix = _("Any other filesystems within the image should be restorable as normal.")
                    is_image = True
                elif absolute_path.endswith(".fsa"):
                    print("Found FSArchiver image " + filename)
                    GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                  _("Scanning: {filename}").format(filename=absolute_path))
                    temp_image_dict = {absolute_path: FsArchiverImage(absolute_path, enduser_filename, filename)}
                    error_suffix = ""
                    is_image = True
                elif ".apt." in absolute_path:
                    # Apart GTK images within a single folder are combined into one ApartGTKImage instance, so ensure
                    # the folder hasn't already been scanned.
                    print("Found Apart GTK image " + filename + " (will include other images in the same folder)")
                    GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                  _("Scanning: {filename}").format(filename=absolute_path))
                    temp_image_dict = {absolute_path: ApartGtkImage(absolute_path)}
                    error_suffix = _("Any other filesystems within the image should be restorable as normal.")
                    # Only 1 Apart GTK image per folder (which may contain a huge number of images, often of the
                    # same partition). Need to add image to the ignore fodler set to prevent double scanning
                    self.ignore_folder_set.add(dirname)
                    is_image = True
                # If haven't found an image for this file, try scanning for QemuImages. Due to slow scan, do not look
                # in subfolders
                else:
                    is_qemu_candidate, extension = QemuImage.is_supported_extension(filename)
                    if is_qemu_candidate:
                        # TODO: Considering skipping raw images, for speedup.
                        # is_raw = QemuImage.does_file_extension_refer_to_raw_image(extension)
                        if QemuImage.has_conflict_img_format_in_same_folder(absolute_path, extension):
                            print("Not considering " + filename + " as QemuImage as found exiting image it probably belongs to")
                        else:
                            print("Found an extension that should be compatible with qemu-nbd: " + filename)
                            timeout_seconds = 10
                            GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                          _("Scanning: {filename}").format(filename=absolute_path)
                                          + " " + _("({timeout_seconds} second timeout)").format(timeout_seconds=timeout_seconds))
                            qemu_img = QemuImage(absolute_path, enduser_filename, timeout_seconds)
                            if qemu_img.has_initialized:
                                temp_image_dict = {absolute_path: qemu_img}

                                error_suffix = _("Support for virtual machine images is still experimental.")
                                is_image = True
                if is_image:
                    image_warning_message = ""
                    for key in temp_image_dict.keys():
                        for warning_dict_key in temp_image_dict[key].warning_dict.keys():
                            image_warning_message += "    " + warning_dict_key + ": "\
                                                     + temp_image_dict[key].warning_dict[warning_dict_key] + "\n"
                    if len(image_warning_message) > 0:
                        self.failed_to_read_image_dict[absolute_path] = _(
                                    "Unable to fully process the image associated with the following partitions:") + "\n" + image_warning_message + error_suffix
                for key in temp_image_dict.keys():
                    self.image_dict[key] = temp_image_dict[key]
        except Exception as e:
            print("Failed to read: " + absolute_path)
            tb = traceback.format_exc()
            self.failed_to_read_image_dict[enduser_filename] = tb
            traceback.print_exc()
        return is_image

    def scan_image_directory(self):
        self.image_dict.clear()
        self.ignore_folder_set.clear()
        self.failed_to_read_image_dict.clear()
        try:
            # list files and directories
            for filename in os.listdir(self.query_path):
                if self.is_stop_requested():
                    break
                abs_base_scan_path = os.path.abspath(join(self.query_path, filename))
                print("Scanning " + abs_base_scan_path)
                if isfile(abs_base_scan_path):
                    print("Scanning file " + abs_base_scan_path)
                    self.scan_file(abs_base_scan_path, filename)
                elif isdir(abs_base_scan_path):
                    GLib.idle_add(self.please_wait_popup.set_secondary_label_text,
                                  _("Scanning: {filename}").format(filename=abs_base_scan_path))
                    # List the subdirectory (1 level deep)
                    for subdir_filename in os.listdir(abs_base_scan_path):
                        if self.is_stop_requested():
                            break
                        absolute_path = join(abs_base_scan_path, subdir_filename)
                        enduser_filename = os.path.join(filename, subdir_filename)
                        if isfile(absolute_path):
                            print("Scanning subdir file " + absolute_path)
                            self.scan_file(absolute_path, enduser_filename)
        except Exception as e:
            tb = traceback.format_exc()
            GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                          "Failed to scan for images: " + tb)
        # Relying on CPython GIL to access the self.image_dict
        GLib.idle_add(self._populate_image_list_table)