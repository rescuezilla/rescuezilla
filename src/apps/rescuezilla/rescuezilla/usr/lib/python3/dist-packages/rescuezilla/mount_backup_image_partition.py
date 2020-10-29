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
import shutil
import subprocess
import threading
import traceback

import gi

from parser.clonezilla_image import ClonezillaImage
from wizard_state import IMAGE_EXPLORER_IMG_PATH

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import PleaseWaitModalPopup, Utility, _



class MountBackupImagePartition:
    @staticmethod
    def mount_backup_image_partition(builder, callback, backup_image, partition_key_to_mount, destination_path):
        please_wait_popup = PleaseWaitModalPopup(builder, title=_("Please wait..."), message=_("Mounting..."))
        please_wait_popup.show()
        thread = threading.Thread(target=MountBackupImagePartition._do_mount_command, args=(please_wait_popup, callback, backup_image, partition_key_to_mount, destination_path, ))
        thread.daemon = True
        thread.start()

    @staticmethod
    def unmount(builder, callback, mounted_path):
        please_wait_popup = PleaseWaitModalPopup(builder, title=_("Please wait..."), message=_("Unmounting..."))
        please_wait_popup.show()
        thread = threading.Thread(target=MountBackupImagePartition._do_unmount_command, args=(please_wait_popup, callback, mounted_path, ))
        thread.daemon = True
        thread.start()

    @staticmethod
    def _do_unmount_command(please_wait_popup, callback, mounted_path):
        try:
            is_unmounted, message = Utility.umount_warn_on_busy(mounted_path)
            if os.path.exists(IMAGE_EXPLORER_IMG_PATH):
                os.remove(IMAGE_EXPLORER_IMG_PATH)
            if not is_unmounted:
                GLib.idle_add(callback, False, message)
                GLib.idle_add(please_wait_popup.destroy)
            else:
                GLib.idle_add(callback, True, "")
                GLib.idle_add(please_wait_popup.destroy)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(callback, False, "Error mounting folder: " + tb)
            GLib.idle_add(please_wait_popup.destroy)

    @staticmethod
    def _do_mount_command(please_wait_popup, callback, image, partition_key, destination_path):
        env = Utility.get_env_C_locale()
        try:
            if not os.path.exists(destination_path) and not os.path.isdir(destination_path):
                os.mkdir(destination_path, 0o755)

            # Unmount and cleanup in case a previous invocation of Rescuezilla didn't cleanup.
            is_unmounted, message = Utility.umount_warn_on_busy(destination_path)
            if not is_unmounted:
                GLib.idle_add(callback, False, message)
                GLib.idle_add(please_wait_popup.destroy)
                return
            if os.path.exists(IMAGE_EXPLORER_IMG_PATH):
                os.remove(IMAGE_EXPLORER_IMG_PATH)

            if isinstance(image, ClonezillaImage):
                if 'type' in image.image_format_dict_dict[partition_key].keys():
                    image_type = image.image_format_dict_dict[partition_key]['type']
                    if image_type == 'partclone':
                        cat_cmd_list = ["cat"] + image.image_format_dict_dict[partition_key]['absolute_filename_glob_list']
                        decompression_cmd_list = ClonezillaImage.get_decompression_command_list(image.image_format_dict_dict[partition_key]['compression'])
                        restore_binary = image.image_format_dict_dict[partition_key]['binary']
                        if shutil.which(restore_binary) is None:
                            GLib.idle_add(callback, False, restore_binary + ": Not found")
                            GLib.idle_add(please_wait_popup.destroy)
                            return
                        restore_command_list = [restore_binary, "--restore", "--restore_raw_file", "--logfile", "/tmp/rescuezilla.image.explorer.partclone.logfile.txt", "--source",
                                                "-", "--output", IMAGE_EXPLORER_IMG_PATH ]

                        flat_command_string = Utility.print_cli_friendly(image_type + " command ",
                                                                         [cat_cmd_list, decompression_cmd_list,
                                                                          restore_command_list])
                        proc = {}
                        proc['cat_' + partition_key] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE,
                                                                         env=env,
                                                                         encoding='utf-8')
                        proc['decompression_' + partition_key] = subprocess.Popen(decompression_cmd_list,
                                                                                   stdin=proc[
                                                                                       'cat_' + partition_key].stdout,
                                                                                   stdout=subprocess.PIPE, env=env,
                                                                                   encoding='utf-8')
                        restore_stdin_proc_key = 'decompression_' + partition_key
                        proc['restore_' + partition_key] = subprocess.Popen(restore_command_list,
                                                                                           stdin=proc[
                                                                                               restore_stdin_proc_key].stdout,
                                                                                           stdout=subprocess.PIPE,
                                                                                           stderr=subprocess.PIPE, env=env,
                                                                                           encoding='utf-8')

                        proc['restore_' + partition_key].poll()
                        proc['cat_' + partition_key].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
                        proc['decompression_' + partition_key].stdout.close()  # Allow p2 to receive a SIGPIPE if p3 exits.
                        stdout, stderr = proc['restore_' + partition_key].communicate()
                        rc = proc['restore_' + partition_key].returncode

                        if rc != 0:
                            GLib.idle_add(callback, False, "Partclone loop device creation failed:\n\n" + flat_command_string + "\n\n" + stdout + " " + stderr)
                            GLib.idle_add(please_wait_popup.destroy)
                            return

                        mount_cmd_list = ['mount', IMAGE_EXPLORER_IMG_PATH, destination_path]
                        process, flat_command_string, failed_message = Utility.run("Mounting selected partition: ",
                                                                                   mount_cmd_list, use_c_locale=False)
                        if process.returncode != 0:
                            GLib.idle_add(callback, False, failed_message)
                            GLib.idle_add(please_wait_popup.destroy)
                            return
                    else:
                        GLib.idle_add(callback, False, "Cannot mount " + partition_key + " with type: " + image_type)
                        GLib.idle_add(please_wait_popup.destroy)
                        return
            elif isinstance(image, RedoBackupLegacyImage):
                base_device_node, partition_number = Utility.split_device_string(partition_key)
                abs_image_list = image.partition_restore_command_dict[partition_number]['abs_image_glob']
                cat_cmd_list = ["cat"] + abs_image_list
                pigz_cmd_list = ["pigz", "--decompress", "--stdout"]
                # Handling Rescuezilla v1.0.5 and Legacy Redo Backup and Recovery images in the same way.
                restore_command = image.partition_restore_command_dict[partition_number]['restore_binary']
                partclone_cmd_list = [restore_command, "--restore", "--restore_raw_file", "--logfile", "/tmp/rescuezilla.image.explorer.partclone.logfile.txt", "--source",
                                                "-", "--output", IMAGE_EXPLORER_IMG_PATH]
                flat_command_string = Utility.print_cli_friendly("command ",
                                                                 [cat_cmd_list, pigz_cmd_list,
                                                                  partclone_cmd_list])
                proc = {}
                proc['cat_' + partition_key] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE,
                                                                env=env,
                                                                encoding='utf-8')
                proc['decompression_' + partition_key] = subprocess.Popen(pigz_cmd_list,
                                                                          stdin=proc[
                                                                              'cat_' + partition_key].stdout,
                                                                          stdout=subprocess.PIPE, env=env,
                                                                          encoding='utf-8')
                restore_stdin_proc_key = 'decompression_' + partition_key
                proc['restore_' + partition_key] = subprocess.Popen(pigz_cmd_list,
                                                                    stdin=proc[restore_stdin_proc_key].stdout,
                                                                    stdout=subprocess.PIPE,
                                                                    stderr=subprocess.PIPE, env=env,
                                                                    encoding='utf-8')

                proc['restore_' + partition_key].poll()
                proc['cat_' + partition_key].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
                proc['decompression_' + partition_key].stdout.close()  # Allow p2 to receive a SIGPIPE if p3 exits.
                stdout, stderr = proc['restore_' + partition_key].communicate()
                rc = proc['restore_' + partition_key].returncode

                if rc != 0:
                    GLib.idle_add(callback, False,
                                  "Partclone loop device creation failed:\n\n" + flat_command_string + "\n\n" + stdout + " " + stderr)
                    GLib.idle_add(please_wait_popup.destroy)
                    return

                mount_cmd_list = ['mount', IMAGE_EXPLORER_IMG_PATH, destination_path]
                process, flat_command_string, failed_message = Utility.run("Mounting selected partition: ",
                                                                           mount_cmd_list, use_c_locale=False)
                if process.returncode != 0:
                    GLib.idle_add(callback, False, failed_message)
                    GLib.idle_add(please_wait_popup.destroy)
                    return

            GLib.idle_add(callback, True, "")
            GLib.idle_add(please_wait_popup.destroy)
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            GLib.idle_add(callback, False, "Error mounting folder: " + tb)
            GLib.idle_add(please_wait_popup.destroy)
