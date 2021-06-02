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
import os
import threading
import traceback

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from utility import PleaseWaitModalPopup, Utility, _


class MountLocalPath:
    def __init__(self, builder, callback, source_path, destination_path):
        self.destination_path = destination_path

        self.source_path = source_path
        self.destination_path = destination_path
        self.callback = callback

        self.requested_stop_lock = threading.Lock()
        self.requested_stop = False

        self.please_wait_popup = PleaseWaitModalPopup(builder, title=_("Please wait..."), message=_("Mounting...") + "\n\n" + _("Close this popup to cancel the mount operation."), on_close_callback=self.cancel_mount)
        self.please_wait_popup.show()
        thread = threading.Thread(target=self._do_mount_command, args=(source_path, destination_path, ))
        thread.daemon = True
        thread.start()

    def cancel_mount(self):
        with self.requested_stop_lock:
            self.requested_stop = True
        return

    def is_stop_requested(self):
        with self.requested_stop_lock:
            return self.requested_stop

    def _do_mount_command(self, source_path, destination_path):
        try:
            if not os.path.exists(destination_path) and not os.path.isdir(destination_path):
                os.mkdir(destination_path, 0o755)

            if self.is_stop_requested():
                GLib.idle_add(self.callback, False, _("Operation cancelled by user."))
                return

            is_unmounted, message = Utility.umount_warn_on_busy(destination_path)
            if not is_unmounted:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, message)
                return

            if self.is_stop_requested():
                GLib.idle_add(self.callback, False, _("Operation cancelled by user."))
                return

            is_unmounted, message = Utility.umount_warn_on_busy(source_path)
            if not is_unmounted:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, message)
                return

            if self.is_stop_requested():
                GLib.idle_add(self.callback, False, _("Operation cancelled by user."))
                return

            mount_cmd_list = ['mount', source_path, destination_path]
            process, flat_command_string, failed_message = Utility.interruptable_run("Mounting selected partition: ", mount_cmd_list, use_c_locale=False, is_shutdown_fn=self.is_stop_requested)
            if process.returncode != 0:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, failed_message)
                return
            else:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, True, "", destination_path)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(self.please_wait_popup.destroy)
            GLib.idle_add(self.callback, False, "Error mounting folder: " + tb)
