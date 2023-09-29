#!/usr/bin/python3
# ----------------------------------------------------------------------
#   Rescuezilla
#   A simple GUI interface that allows bare-metal backup and restore.
#   https://www.patreon.com/join/rescuezilla
# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
#   Copyright (C) 2019-2023 Rescuezilla.com <rescuezilla@gmail.com>
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
import gettext
import os
import sys

import argparse
import gi

from backup_manager import BackupManager
from cli.args import parse_arguments
from parser.clonezilla_image import ClonezillaImage
from parser.metadata_only_image import MetadataOnlyImage
from partitions_to_restore import PartitionsToRestore
from ui_manager import UiManager
from clone_manager import CloneManager
from drive_query import CliDriveQuery, DriveQueryInternal
from image_explorer_manager import ImageExplorerManager
from restore_manager import RestoreManager
from utility import Utility, ErrorMessageModalPopup
from verify_manager import VerifyManager

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib


from handler import Handler


def is_root():
    return os.geteuid() == 0


def _exit(is_success):
    if is_success:
        exit(0)
    else:
        exit(1)


def main():
    if not is_root():
        print("Rescuezilla must run as root.")
        exit(0)

    gettext_translation_search_path = sys.base_prefix + "/share/locale/{LANGUAGE,LC_ALL,LC_MESSAGES,LANG}/LC_MESSAGES/rescuezilla.mo"
    print("Setting GTK translation domain by searching: " + gettext_translation_search_path)
    # Set the translation domain folder:
    gettext.bindtextdomain('rescuezilla')
    # Query the translation
    gettext.textdomain('rescuezilla')

    print("WARNING: Rescuezilla's command-line interface should be considered as EXPERIMENTAL and UNSTABLE")
    print("WARNING: Command-line interface behavior may change between versions without notice.")
    parser = argparse.ArgumentParser(prog="rescuezillapy", description="Rescuezilla")
    args = parse_arguments(parser=parser)

    memory_bus_width = Utility.get_memory_bus_width().strip()
    version = Utility.read_file_into_string("/usr/share/rescuezilla/VERSION").strip()
    commit_date = Utility.read_file_into_string("/usr/share/rescuezilla/GIT_COMMIT_DATE").strip()
    human_readable_version = version + " (" + memory_bus_width + ") " + commit_date

    if args.command is None:
        # No arguments
        launch_gui(human_readable_version=human_readable_version)
    else:
        cli_mode(args=args,
                 human_readable_version=human_readable_version)


def cli_mode(args: argparse.Namespace,
             human_readable_version: str):
        print(str(args))

        cli_ui_manager = UiManager()
        if args.command == "backup":
            backup_manager = BackupManager(ui_manager=cli_ui_manager,
                                           human_readable_version=human_readable_version)
            cli_drive_query = CliDriveQuery()
            drive_query = DriveQueryInternal(ui_manager=cli_drive_query)
            drive_state = drive_query._do_drive_query()
            backup_manager.start_backup(selected_drive_key=args.source,
                                        partitions_to_backup=args.partitions,
                                        drive_state=drive_state,
                                        dest_dir=args.destination,
                                        backup_notes=args.description,
                                        compression_dict={"format": args.compression_format, "level": args.compression_level},
                                        is_rescue=args.rescue,
                                        completed_backup_callback=cli_ui_manager._on_operation_completed_callback,
                                        metadata_only_image_to_annotate=None,
                                        on_separate_thread=False)
        elif args.command == "restore":
            image = get_clonezilla_img(source_path=args.source)
            restore_manager = RestoreManager(ui_manager=cli_ui_manager)
            # Get the partitions in the image, and the partitions on the destination disk, with the assumption the
            # partition table is being overwritten
            restore_mapping_dict = PartitionsToRestore.get_partition_to_restore(selected_image=image,
                                                                                dest_drive_node=args.destination,
                                                                                partitions_to_restore=args.partitions)
            restore_manager.start_restore(image=image,
                                          restore_destination_drive=args.destination,
                                          restore_mapping_dict=restore_mapping_dict,
                                          is_overwriting_partition_table=args.overwrite_partition_table,
                                          is_rescue=args.rescue,
                                          completed_callback=cli_ui_manager._on_operation_completed_callback,
                                          on_separate_thread=False)
        elif args.command == "clone":
            backup_manager = BackupManager(ui_manager=cli_ui_manager,
                                           human_readable_version=human_readable_version)
            cli_drive_query = CliDriveQuery()
            drive_query = DriveQueryInternal(ui_manager=cli_drive_query)
            drive_state = drive_query._do_drive_query()
            restore_manager = RestoreManager(ui_manager=cli_ui_manager)
            clone_manager = CloneManager(ui_manager=cli_ui_manager,
                                         backup_manager=backup_manager,
                                         restore_manager=restore_manager)
            metadata_img = get_metadata_only_img(source_drive_key=args.source)
            # Get the partitions in the image, and the partitions on the destination disk, with the assumption the
            # partition table is being overwritten
            clone_mapping_dict = PartitionsToRestore.get_partition_to_restore(selected_image=metadata_img,
                                                                              dest_drive_node=args.destination,
                                                                              partitions_to_restore=args.partitions)
            clone_manager.start_clone(image=metadata_img,
                                      clone_destination_drive=args.destination,
                                      clone_mapping_dict=clone_mapping_dict,
                                      drive_state=drive_state,
                                      is_overwriting_partition_table=args.overwrite_partition_table,
                                      is_rescue=args.rescue,
                                      completed_callback=cli_ui_manager._on_operation_completed_callback,
                                      on_separate_thread=False)
        elif args.command == "verify":
            verify_manager = VerifyManager(ui_manager=cli_ui_manager)
            image = get_clonezilla_img(source_path=args.source)
            verify_manager.start_verify(image_list=[image],
                                        completed_callback=cli_ui_manager._on_operation_completed_callback,
                                        on_separate_thread=False)
        elif args.command == "mount":
            image_explorer_manager = ImageExplorerManager()
            image_explorer_manager.mount_partition(selected_partition_key=args.partitions)
        elif args.command == "umount":
            image_explorer_manager = ImageExplorerManager()
            #image_explorer_manager.umount_partition(selected_partition_key=args.partitions)
        else:
            print("unknown mode")

# Get Clonezilla image for CLI purposes
# TODO: Better abstract logic of ImageFolderQuery, so this logic can be removed, and CLI works with all supported
# image types
def get_clonezilla_img(source_path: str):
    if not source_path.endswith("parts"):
        source_path = os.path.join(source_path, "parts")
    dirname = os.path.dirname(source_path)
    abspath = os.path.abspath(source_path)
    img = ClonezillaImage.get_clonezilla_image_dict(abspath, dirname)
    # HACK: return first Clonezilla disk in image (a single clonezilla image can hold multiple disks)
    return img[list(img.keys())[0]]

# TODO: Better abstract logic from CloneManager, so this logic can be removed, and CLI works with all supported
def get_metadata_only_img(source_drive_key: str):
    # FIXME: Do on separate thread, with please wait popup. Like eg, mounting paths
    print("Creating MetadataOnlyImage (currently temporarily done on UI thread). This may take a moment...")
    source_drive_metadata_only_image = MetadataOnlyImage(source_drive_key)
    if len(source_drive_metadata_only_image.warning_dict) > 0:
        error_msg = ""
        for value in source_drive_metadata_only_image.warning_dict.values():
            error_msg += value + "\n"
            print(("Unable to process {source}:").format(source=source_drive_key) + "\n\n" + error_msg)
    return source_drive_metadata_only_image

def launch_gui(human_readable_version: str):
    builder = Gtk.Builder()
    builder.set_translation_domain('rescuezilla')
    # Use the GTKBuilder to dynamically construct all the UI widget objects as defined in the GTKBuilder .glade XML
    # file. This file may be edited using the Glade UI widget editor. It is sometimes required to edit the XML
    # directly a text editor, because Glade occasionally has some user-interface limitations.
    builder.add_from_file("/usr/share/rescuezilla/rescuezilla.glade")

    handler = Handler(builder,
                      human_readable_version=human_readable_version)
    # Connect the handler object for the GUI callbacks. This handler manages the entire application state.
    builder.connect_signals(handler)

    # Do not show the GTKNotebook tab menu. For each mode (including mode selection), the pages of the wizard are
    # achieved through a GTKNotebook, which is a tabbed container that provides a function to switch between pages in
    # the wizard. The tab menu itself is useful when viewing and editing the GUI with Glade, but should not be
    # displayed to end-users because the application design relies on users not being able to skip steps.
    builder.get_object("mode_tabs").set_show_tabs(False)
    builder.get_object("backup_tabs").set_show_tabs(False)
    builder.get_object("restore_tabs").set_show_tabs(False)
    builder.get_object("verify_tabs").set_show_tabs(False)
    builder.get_object("clone_tabs").set_show_tabs(False)
    builder.get_object("image_explorer_tabs").set_show_tabs(False)

    # Display the main GTK window
    win = builder.get_object("main_window")
    win.show()

    nbd_module_missing_msg = "The 'nbd' (Network Block Device) kernel module is not loaded.\n\nRescuezilla will load it with modprobe, but it appears to take time to fully initialize.\n\nFor the best experience, add 'nbd' to /etc/modules and reboot before using Rescuezilla."
    process, flat_command_string, fail_description = Utility.run("Querying for NBD module", ["lsmod"], use_c_locale=True)
    if "nbd" not in process.stdout:
        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, builder, nbd_module_missing_msg)

    # Set the background color of the Rescuezilla banner box (using CSS) [1] to the same dark blue background color
    # used by the fixed-sized banner image, so that the banner looks good even when resizing the window.
    # [1] Adapted from: https://github.com/zim-desktop-wiki/zim-desktop-wiki/blob/master/zim/gui/widgets.py
    banner_image_eventbox = builder.get_object("banner_image_eventbox")
    # Set the custom CSS using the GTK 'name' attribute (note this is different to the 'id' attribute)
    css_text = '#banner { background-color: #345278; }'
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(css_text.encode('UTF-8'))
    banner_style = banner_image_eventbox.get_style_context()
    banner_style.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # Starts the GTK event loop. As with other user-interface libraries, the GTK event loop is single-threaded. This
    # GTK loop simply reads a queue of events (mouse click on button, timeout of a countdown timer), and executes the
    # handler functions that were registered earlier. To exit the main loop, a handler function can run Gtk.main_quit().
    Gtk.main()


if __name__ == "__main__":
    main()
