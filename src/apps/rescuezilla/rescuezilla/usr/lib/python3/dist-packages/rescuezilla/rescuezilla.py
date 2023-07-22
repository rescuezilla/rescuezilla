#!/usr/bin/python3
# ----------------------------------------------------------------------
#   Rescuezilla
#   A simple GUI interface that allows bare-metal backup and restore.
#   https://www.patreon.com/join/rescuezilla
# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
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
import gettext
import os
import sys

import gi

from utility import Utility, ErrorMessageModalPopup

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib


from handler import Handler


def is_root():
    return os.geteuid() == 0


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

    builder = Gtk.Builder()
    builder.set_translation_domain('rescuezilla')
    # Use the GTKBuilder to dynamically construct all the UI widget objects as defined in the GTKBuilder .glade XML
    # file. This file may be edited using the Glade UI widget editor. It is sometimes required to edit the XML
    # directly a text editor, because Glade occasionally has some user-interface limitations.
    builder.add_from_file("/usr/share/rescuezilla/rescuezilla.glade")

    handler = Handler(builder)
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
