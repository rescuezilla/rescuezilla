# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
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
import tempfile
import threading
import traceback

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from utility import PleaseWaitModalPopup, Utility, _



class MountNetworkPath:
    def __init__(self, builder, callback, mode, destination_path):
        # Lowercase mode (eg "backup", "restore", "verify")
        mode_prefix = mode.name.lower()
        settings = {
            'server': builder.get_object(mode_prefix + "_network_server").get_text(),
            'username': builder.get_object(mode_prefix + "_network_username").get_text(),
            'password': builder.get_object(mode_prefix + "_network_password").get_text(),
            'domain': builder.get_object(mode_prefix + "_network_domain").get_text(),
            'version': builder.get_object(mode_prefix + "_network_version").get_text(),
            'destination_path': destination_path}

        # restore_network_version
        self.callback = callback
        self.please_wait_popup = PleaseWaitModalPopup(builder, title=_("Please wait..."), message=_("Mounting..."))
        self.please_wait_popup.show()
        thread = threading.Thread(target=self._do_mount_command, args=(settings,))
        thread.daemon = True
        thread.start()

    def _do_mount_command(self, settings):
        destination_path = settings['destination_path']
        try:
            if not os.path.exists(destination_path) and not os.path.isdir(destination_path):
                os.mkdir(destination_path, 0o755)

            is_unmounted, message = Utility.umount_warn_on_busy(destination_path)
            if not is_unmounted:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.please_wait_popup.destroy)
                return

            smb_arguments = ""
            credentials_string = ""

            tmp = tempfile.NamedTemporaryFile()
            if settings['username'] != "":
                credentials_string = "username=" + settings['username'] + "\n"
            if settings['password'] != "":
                credentials_string += "password=" + settings['password'] + "\n"
            if settings['domain'] != "":
                credentials_string += "domain=" + settings['domain'] + "\n"

            if settings['username'] != "" or settings['password'] != "":
                smb_arguments += "credentials=" + tmp.name

            if credentials_string == "":
                smb_arguments += "guest"
            elif settings['password'] == "":
                    smb_arguments += ",guest"

            if settings['version'] != "":
                smb_arguments += "version=" + settings['version']



            with open(tmp.name, 'w') as f:
                f.write(credentials_string)
                f.flush()
                mount_cmd_list = ['mount.cifs', settings['server'], settings['destination_path'], "-o", smb_arguments]
                mount_process, mount_flat_command_string, mount_failed_message = Utility.run("Mounting network shared folder: ", mount_cmd_list, use_c_locale=False)

            shred_cmd_list = ['shred', "-u", tmp.name]
            shred_process, shred_flat_command_string, failed_message = Utility.run("Shredding credentials temp file: ", shred_cmd_list, use_c_locale=False)
            if shred_process.returncode != 0:
                GLib.idle_add(self.callback, False, failed_message)
                GLib.idle_add(self.please_wait_popup.destroy)
                return

            if mount_process.returncode != 0:
                check_password_msg = _("Please ensure the username, password and other fields provided are correct, and try again.")
                GLib.idle_add(self.callback, False, mount_failed_message + "\n\n" + check_password_msg)
                GLib.idle_add(self.please_wait_popup.destroy)
                return
            else:
                GLib.idle_add(self.callback, True, "", destination_path)
                GLib.idle_add(self.please_wait_popup.destroy)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(self.callback, False, "Error mounting folder: " + tb)
            GLib.idle_add(self.please_wait_popup.destroy)