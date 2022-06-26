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
import tempfile
import threading
import traceback

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from utility import PleaseWaitModalPopup, Utility, _



class MountNetworkPath:
    def __init__(self, builder, callback, mode, network_widget_dict, destination_path):
        # Lowercase mode (eg "backup", "restore", "verify")
        mode_prefix = mode.name.lower()
        settings = {
            'server': network_widget_dict["network_server"][mode].get_text().strip(),
            'username': network_widget_dict["network_username"][mode].get_text().strip(),
            # For protocols that specify the remote path separately from the server
            'remote_path': network_widget_dict["network_remote_path"][mode].get_text().strip(),
            # NOT stripping whitespace from the password
            'password': network_widget_dict["network_password"][mode].get_text(),
            'domain': network_widget_dict["network_domain"][mode].get_text().strip(),
            'version': Utility.get_combobox_key(network_widget_dict["network_version_combobox"][mode]),
            'ssh_idfile': network_widget_dict["network_ssh_idfile"][mode].get_text().strip(),
            'destination_path': destination_path,
            'port': network_widget_dict["network_port"][mode].get_text().strip(),
        }

        network_protocol_key = Utility.get_combobox_key(network_widget_dict['network_protocol_combobox'][mode])
        # restore_network_version
        self.callback = callback

        self.requested_stop_lock = threading.Lock()
        self.requested_stop = False

        self.please_wait_popup = PleaseWaitModalPopup(builder, title=_("Please wait..."), message=_("Mounting...") + "\n\n" + _("Close this popup to cancel the mount operation."), on_close_callback=self.cancel_mount)
        self.please_wait_popup.show()
        if network_protocol_key == "SMB":
            thread = threading.Thread(target=self._do_smb_mount_command, args=(settings,))
        elif network_protocol_key == "SSH":
            thread = threading.Thread(target=self._do_ssh_mount_command, args=(settings,))
        elif network_protocol_key == "NFS":
            thread = threading.Thread(target=self._do_nfs_mount_command, args=(settings,))
        else:
            raise ValueError("Unknown network protocol: " + network_protocol_key)
        thread.daemon = True
        thread.start()

    def cancel_mount(self):
        with self.requested_stop_lock:
            self.requested_stop = True
        return

    def is_stop_requested(self):
        with self.requested_stop_lock:
            return self.requested_stop

    def _do_smb_mount_command(self, settings):
        destination_path = settings['destination_path']
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

            smb_arguments = ""
            credentials_string = ""

            tmp = tempfile.NamedTemporaryFile()
            if settings['username'] != "":
                credentials_string = "username=" + settings['username'] + "\n"
            else:
                # The mount.cifs man page states "If [the username field] is not given, then the environment variable
                # USER is used". However in practice, for anonymous Windows network shared folders some username must
                # be specified. Trying to pass in a blank username returns makes mount.cifs return "username
                # specified with no parameter". Some users have set an asterisk character [1], but any username works.
                # Therefore choosing using 'rescuezilla' to provide more descriptive logs for system administrators.
                # https://github.com/rescuezilla/rescuezilla/issues/190
                credentials_string = "username=rescuezilla" + "\n"
            if settings['password'] != "":
                credentials_string += "password=" + settings['password'] + "\n"
            if settings['domain'] != "":
                credentials_string += "domain=" + settings['domain'] + "\n"
            smb_arguments += "credentials=" + tmp.name

            if settings['password'] == "":
                    smb_arguments += ",guest"

            # Version is always provided (using "default" string in most cases). Older versions of mount.cifs
            # potentially may not support 'default' (at least the man pages don't cover it)
            if smb_arguments != "":
                smb_arguments += ","
            smb_arguments += "vers=" + settings['version']

            with open(tmp.name, 'w') as f:
                f.write(credentials_string)
                f.flush()
                mount_cmd_list = ['mount.cifs', settings['server'], settings['destination_path'], "-o", smb_arguments]
                mount_process, mount_flat_command_string, mount_failed_message = Utility.interruptable_run("Mounting SMB/CIFS network shared folder: ", mount_cmd_list, use_c_locale=False, is_shutdown_fn=self.is_stop_requested)

            shred_cmd_list = ['shred', tmp.name]
            shred_process, shred_flat_command_string, failed_message = Utility.run("Shredding credentials temp file: ", shred_cmd_list, use_c_locale=False)
            # Delete temp file
            tmp.close()
            if shred_process.returncode != 0:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, failed_message)
                return

            if mount_process.returncode != 0:
                check_password_msg = _("Please ensure the username, password and other fields provided are correct, and try again.")
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, mount_failed_message + "\n\n" + check_password_msg)
                return
            else:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, True, "", destination_path)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(self.please_wait_popup.destroy)
            GLib.idle_add(self.callback, False, "Error mounting SMB/CIFS folder: " + tb)

    def _do_ssh_mount_command(self, settings):
        destination_path = settings['destination_path']
        try:
            if not os.path.exists(destination_path) and not os.path.isdir(destination_path):
                os.mkdir(destination_path, 0o755)

            is_unmounted, message = Utility.umount_warn_on_busy(destination_path)
            if not is_unmounted:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, message)
                return

            source_string = ""

            # Username is optional in SSH, it uses the current user if not specified.
            if settings['username'] != "":
                source_string = settings['username'] + "@"

            if settings['server'] != "":
                source_string += settings['server']
            else:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, "Must specify server.")
                return

            if settings['remote_path'] != "":
                source_string += ":" + settings['remote_path']
            else:
                # If no remote path specified, assume the user wants to mount the root directory of their remote server.
                source_string += ":/"

            mount_cmd_list = ["sshfs", source_string, settings['destination_path']]

            if settings['password'] == "" and settings['ssh_idfile'] == "":
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, _("Must provide either password or SSH identity file."))
                return

            ssh_cmd = ""
            tmp = tempfile.NamedTemporaryFile(delete=False)
            if settings['password'] != "":
                with open(tmp.name, 'w') as f:
                    f.write(settings['password'] + "\n")
                    f.flush()
                    ssh_cmd += "sshpass -f " + tmp.name + " "

            ssh_port = "22"
            if settings['port'] != "":
                ssh_port = settings['port']

            ssh_cmd += f"ssh -p {ssh_port} -o StrictHostKeyChecking=no"
            if settings['ssh_idfile'] != "":
                ssh_cmd += ",IdentityFile=" + settings['ssh_idfile'] + ",BatchMode=yes"
            mount_cmd_list.append('-o')
            # In the Python subprocess.run() cmd_list, the ssh_cmd variable cannot be surrounded by quotes
            mount_cmd_list.append('ssh_command=' + ssh_cmd)

            mount_process, mount_flat_command_string, mount_failed_message = Utility.interruptable_run("Mounting network shared folder with SSH: ", mount_cmd_list, use_c_locale=False, is_shutdown_fn=self.is_stop_requested)
            shred_cmd_list = ['shred', tmp.name]
            shred_process, shred_flat_command_string, failed_message = Utility.run(
                "Shredding credentials temp file: ", shred_cmd_list, use_c_locale=False)
            # Delete temp file
            os.remove(tmp.name)
            if shred_process.returncode != 0:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, failed_message)
                return

            if mount_process.returncode != 0:
                check_password_msg = _("Please ensure the username, password and other fields provided are correct, and try again.")
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, mount_failed_message + "\n\n" + check_password_msg)
                return
            else:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, True, "", destination_path)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(self.please_wait_popup.destroy)
            GLib.idle_add(self.callback, False, "Error mounting SSH folder: " + tb)

    def _do_nfs_mount_command(self, settings):
        destination_path = settings['destination_path']
        try:
            if not os.path.exists(destination_path) and not os.path.isdir(destination_path):
                os.mkdir(destination_path, 0o755)

            is_unmounted, message = Utility.umount_warn_on_busy(destination_path)
            if not is_unmounted:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, message)
                return

            if settings['server'] != "":
                server = settings['server']
            else:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, "Must specify server.")
                return

            if settings['remote_path'] != "":
                exported_dir = settings['remote_path']
            else:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, "Must specify exported directory.")
                return

            mount_cmd_list = ["mount.nfs", server + ":" + exported_dir, settings['destination_path']]
            mount_process, mount_flat_command_string, mount_failed_message = Utility.interruptable_run("Mounting network shared folder with NFS: ", mount_cmd_list, use_c_locale=False, is_shutdown_fn=self.is_stop_requested)
            if mount_process.returncode != 0:
                check_password_msg = _("Please ensure the server and exported path are correct, and try again.")
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, False, mount_failed_message + "\n\n" + check_password_msg)
                return
            else:
                GLib.idle_add(self.please_wait_popup.destroy)
                GLib.idle_add(self.callback, True, "", destination_path)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(self.please_wait_popup.destroy)
            GLib.idle_add(self.callback, False, "Error mounting NFS folder: " + tb)
