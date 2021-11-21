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
import collections
import json
import os
import pprint
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime

import gi

from image_explorer_manager import ImageExplorerManager
from parser.blkid import Blkid
from parser.combined_drive_state import CombinedDriveState
from parser.os_prober import OsProber
from parser.parted import Parted
from parser.sfdisk import Sfdisk
from utility import PleaseWaitModalPopup, Utility, _, ErrorMessageModalPopup
from wizard_state import IMAGE_EXPLORER_DIR, RESCUEZILLA_MOUNT_TMP_DIR

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


class DriveQuery:
    def __init__(self, builder, drive_list_store, save_partition_list_store, mount_partition_list_store):
        self.builder = builder
        self.drive_list_store = drive_list_store
        self.save_partition_list_store = save_partition_list_store
        self.mount_partition_list_store = mount_partition_list_store
        self.win = self.builder.get_object("main_window")
        self._is_displaying_advanced_information_lock = threading.Lock()
        self._is_displaying_advanced_information = False

    def cancel_query(self):
        with self.requested_stop_lock:
            self.requested_stop = True
        return

    def is_stop_requested(self):
        with self.requested_stop_lock:
            return self.requested_stop

    def start_query(self, error_message_callback):
        print("Starting drive query...")
        self.win.set_sensitive(False)
        self.requested_stop_lock = threading.Lock()
        self.requested_stop = False

        self.please_wait_popup = PleaseWaitModalPopup(self.builder, title=_("Please wait..."), message=_("Identifying disk drives..."), on_close_callback=self.cancel_query)
        self.please_wait_popup.show()
        self.error_message_callback = error_message_callback

        thread = threading.Thread(target=self._do_drive_query_wrapper)
        thread.daemon = True
        thread.start()

    def set_show_hidden_information(self, is_displaying_advanced_information):
        # User-interface sensitivity acting as further crude protection prevent inconsistent state. TODO: Improve this design.
        with self._is_displaying_advanced_information_lock:
            self._is_displaying_advanced_information = is_displaying_advanced_information

    def populate_drive_selection_table(self):
        self.drive_list_store.clear()
        index = 0
        for drive_key in self.drive_state.keys():
            try:
                drive = self.drive_state[drive_key]
                with self._is_displaying_advanced_information_lock:
                    if self._is_displaying_advanced_information:
                        # Display a advanced-user partition name eg, "nvme0n1". Users coming from Clonezilla will often
                        # like to know the device node.
                        human_friendly_drive_name = drive_key
                    else:
                        # Display a user-friendly drive name eg, "3" to refer to nvme0n1.Some Rescuezilla users may prefer
                        # drives identified by a simple digit (eg, drive #3), because they may not understand what a short
                        # device node like "nvme0n1" means.
                        human_friendly_drive_name = "#" + str(index + 1)
                        if (drive['type'] != 'disk' and not drive['type'].startswith("raid"))\
                                or drive['has_raid_member_filesystem'] or 'nbd' in drive_key :
                            # Hiding LVMs, loop devices, empty drives etc from initial drive selection list. This
                            # should greatly reduce the risk a user accidentally picks a logical volume (of their
                            # say, encrypted Debian system) when they were actually intending on picking the entire
                            # block device (including boot partition etc).
                            #
                            # Don't display non-block device if we are hiding them (like /dev/loop)
                            continue

                flattened_partition_list = CombinedDriveState.flatten_partition_list(drive)
                print("For key " + drive_key + ", flattened partition list is " + flattened_partition_list)
                enduser_readable_capacity = Utility.human_readable_filesize(int(drive['capacity']))
                self.drive_list_store.append([drive_key, human_friendly_drive_name, enduser_readable_capacity,
                                              drive['model'], drive['serial'], flattened_partition_list])
                index = index + 1
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                print("Could not process " + drive_key)
                continue
        # TODO: Don't populate mount partition here
        self.populate_mount_partition_table()
        if self.please_wait_popup is not None:
            self.please_wait_popup.destroy()
            self.please_wait_popup = None

    def populate_partition_selection_table(self, drive_key):
        print('Received drive key ' + drive_key)
        print('drive state is ' + str(self.drive_state))
        self.save_partition_list_store.clear()

        try:
            if 'partitions' in self.drive_state[drive_key].keys():
                for partition_key in self.drive_state[drive_key]['partitions'].keys():
                    flattened_partition_description = CombinedDriveState.flatten_partition_description(self.drive_state, drive_key, partition_key)
                    # Add row that's ticked
                    self.save_partition_list_store.append([partition_key, True, flattened_partition_description])
            else:
                # Add the drive itself
                flattened_partition_description = CombinedDriveState.flatten_partition_description(self.drive_state,
                                                                                                   drive_key, drive_key)
                # Add row that's ticked
                self.save_partition_list_store.append([drive_key, True, flattened_partition_description])
        except Exception as exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            ErrorMessageModalPopup.display_nonfatal_warning_message(self.builder, tb)
        return

    def populate_mount_partition_table(self, ignore_drive_key=None):
        print('drive state is ' + str(self.drive_state))
        self.mount_partition_list_store.clear()
        index = 0
        for drive_key in self.drive_state.keys():
            try:
                if drive_key == ignore_drive_key or 'nbd' in drive_key:
                    continue
                if 'partitions' not in self.drive_state[drive_key].keys():
                    continue
                for partition_key in self.drive_state[drive_key]['partitions'].keys():
                    with self._is_displaying_advanced_information_lock:
                        if self._is_displaying_advanced_information:
                            # Display a advanced-user partition name eg, "nvme0n1p1".
                            human_friendly_partition_name = partition_key
                        else:
                            if self.drive_state[drive_key]['type'] == 'loop' or self.drive_state[drive_key]['has_raid_member_filesystem']:
                                # Don't display certain non-block device if user has chosen to hide them.
                                # TODO: Evaluate other partition types to be hidden.
                                continue
                            # Display a advanced-user partition name eg, "#4".
                            human_friendly_partition_name = "#" + str(index + 1)
                        flattened_partition_description = CombinedDriveState.flatten_partition_description(self.drive_state, drive_key, partition_key)
                    if 'size' in self.drive_state[drive_key]['partitions'][partition_key].keys():
                        size_in_bytes = self.drive_state[drive_key]['partitions'][partition_key]['size']
                        enduser_readable_size = Utility.human_readable_filesize(int(size_in_bytes))
                    else:
                        enduser_readable_size = "unknown_size"
                    self.mount_partition_list_store.append([partition_key, human_friendly_partition_name, enduser_readable_size, flattened_partition_description])
                    index = index + 1
            except Exception as exception:
                tb = traceback.format_exc()
                traceback.print_exc()
                ErrorMessageModalPopup.display_nonfatal_warning_message(self.builder, tb)
        return

    def _get_parted_cmd_list(self, partition_longdevname):
        # TODO: Consider switching to using parted's --machine flag to get easily parseable output for internal
        # TODO: Rescuezilla usage. Note: The Clonezilla image format does *not* use the --machine flag.
        return ["parted", "-s", partition_longdevname, "unit", "B", "print"]

    def _get_sfdisk_cmd_list(self, partition_longdevname):
        return ["sfdisk", "--dump", partition_longdevname]

    def _do_drive_query_wrapper(self):
        try:
            self._do_drive_query()
        except Exception as exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            GLib.idle_add(self.error_message_callback, False, _("Error querying drives: ") + tb)
            return

    def _do_drive_query(self):
        env_C_locale = Utility.get_env_C_locale()

        drive_query_start_time = datetime.now()

        GLib.idle_add(self.please_wait_popup.set_secondary_label_text, _("Unmounting: {path}").format(path=IMAGE_EXPLORER_DIR))
        returncode, failed_message = ImageExplorerManager._do_unmount(IMAGE_EXPLORER_DIR)
        if not returncode:
            GLib.idle_add(self.error_message_callback, False, _("Unable to shutdown Image Explorer") + "\n\n" + failed_message)
            GLib.idle_add(self.please_wait_popup.destroy)
            return

        if self.is_stop_requested():
            GLib.idle_add(self.error_message_callback, False, _("Operation cancelled by user."))
            return

        GLib.idle_add(self.please_wait_popup.set_secondary_label_text,  _("Unmounting: {path}").format(path=RESCUEZILLA_MOUNT_TMP_DIR))
        returncode, failed_message = ImageExplorerManager._do_unmount(RESCUEZILLA_MOUNT_TMP_DIR)
        if not returncode:
            GLib.idle_add(self.error_message_callback, False, _("Unable to unmount {path}").format(path=RESCUEZILLA_MOUNT_TMP_DIR) + "\n\n" + failed_message)
            GLib.idle_add(self.please_wait_popup.destroy)
            return

        if self.is_stop_requested():
            GLib.idle_add(self.error_message_callback, False, _("Operation cancelled by user."))
            return

        lsblk_cmd_list = ["lsblk", "-o", "KNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL", "--paths", "--bytes", "--json"]
        blkid_cmd_list = ["blkid"]
        os_prober_cmd_list = ["os-prober"]

        lsblk_json_dict = {}
        blkid_dict = {}
        os_prober_dict = {}
        parted_dict_dict = collections.OrderedDict([])
        sfdisk_dict_dict = collections.OrderedDict([])

        # Clonezilla combines drive, partition and filesystem from multiple data sources (lsblk, blkid, parted etc)
        # Rescuezilla continues this approach to reach best possible Clonezilla compatibility.
        #
        # However this sequential querying is slow. A parallel approach should be in theory much faster (but might be
        # less reliable if internal commands are creating file locks etc.)
        #
        # In practice, the sequential approach was about 25% faster than a first-cut (polling-based) parallel approach.
        # Parallel mode currently disabled, but kept for further development/analysis.
        mode = "sequential-drive-query"
        if mode == "sequential-drive-query":
            print("Running drive query in sequential mode")

            # TODO: Run with Utility.interruptable_run() so that even long-lived commands can have a signal sent to it
            #  to shutdown early.

            # Not checking return codes here because Clonezilla does not, and some of these commands are expected to
            # fail. The Utility.run() command prints the output to stdout.
            GLib.idle_add(self.please_wait_popup.set_secondary_label_text,  _("Running: {app}").format(app="lsblk"))
            process, flat_command_string, fail_description = Utility.run("lsblk", lsblk_cmd_list, use_c_locale=True)
            lsblk_json_dict = json.loads(process.stdout)

            if self.is_stop_requested():
                GLib.idle_add(self.error_message_callback, False, _("Operation cancelled by user."))
                return

            GLib.idle_add(self.please_wait_popup.set_secondary_label_text,  _("Running: {app}").format(app="blkid"))
            process, flat_command_string, fail_description = Utility.run("blkid", blkid_cmd_list, use_c_locale=True)
            blkid_dict = Blkid.parse_blkid_output(process.stdout)

            if self.is_stop_requested():
                GLib.idle_add(self.error_message_callback, False, _("Operation cancelled by user."))
                return

            GLib.idle_add(self.please_wait_popup.set_secondary_label_text, _("Running: {app}").format(app="os-prober"))
            # Use os-prober to get OS information (running WITH original locale information
            process, flat_command_string, fail_description = Utility.run("osprober", os_prober_cmd_list, use_c_locale=True)
            os_prober_dict = OsProber.parse_os_prober_output(process.stdout)

            if self.is_stop_requested():
                GLib.idle_add(self.error_message_callback, False, _("Operation cancelled by user."))
                return


            for lsblk_dict in lsblk_json_dict['blockdevices']:
                partition_longdevname = lsblk_dict['name']
                print("Going to run parted and sfdisk on " + partition_longdevname)
                try:
                    GLib.idle_add(self.please_wait_popup.set_secondary_label_text, _("Running {app} on {device}").format(app="parted", device=partition_longdevname))
                    process, flat_command_string, fail_description = Utility.run("parted", self._get_parted_cmd_list(partition_longdevname), use_c_locale=True)
                    if "unrecognized disk label" not in process.stderr:
                        parted_dict_dict[partition_longdevname] = Parted.parse_parted_output(process.stdout)
                    else:
                        print("Parted says " + process.stderr)

                    if self.is_stop_requested():
                        GLib.idle_add(self.error_message_callback, False, _("Operation cancelled by user."))
                        return
                    GLib.idle_add(self.please_wait_popup.set_secondary_label_text, _("Running {app} on {device}").format(app="sfdisk", device=partition_longdevname))
                    process, flat_command_string, fail_description = Utility.run("sfdisk", self._get_sfdisk_cmd_list(partition_longdevname), use_c_locale=True)
                    sfdisk_dict_dict[partition_longdevname] = Sfdisk.parse_sfdisk_dump_output(process.stdout)
                    if self.is_stop_requested():
                        GLib.idle_add(self.error_message_callback, False, _("Operation cancelled by user."))
                        return

                except Exception:
                    print("Could run run parted on " + partition_longdevname)
        elif mode == "parallel-drive-query":
            print("Running drive query in parallel mode")
            # Launch drive query in parallel. Parallel Python subprocess.Popen() approach adapted from [1]
            # [1] https://stackoverflow.com/a/636601
            cmd_dict = {
                ('lsblk', ""): subprocess.Popen(lsblk_cmd_list, env=env_C_locale, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                encoding="utf-8", universal_newlines=True),
                ('blkid', ""): subprocess.Popen(blkid_cmd_list, env=env_C_locale, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                encoding="utf-8", universal_newlines=True),
                ('os_prober', ""): subprocess.Popen(os_prober_cmd_list, env=env_C_locale, stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE, encoding="utf-8", universal_newlines=True),
            }
            while cmd_dict:
                print("drive_query_process is length " + str(len(cmd_dict)) + " with contents " + str(cmd_dict))
                for key in list(cmd_dict.keys()):
                    proc = cmd_dict[key]
                    retcode = proc.poll()
                    if retcode is not None:  # Process finished.
                        cmd_dict.pop(key, None)
                        if key[0] == "lsblk" and retcode == 0:
                            # lsblk is complete, partition information can be used to launch the parted/sfdisk
                            lsblk_json_dict = json.loads(proc.stdout.read())
                            for lsblk_dict in lsblk_json_dict['blockdevices']:
                                partition_longdevname = lsblk_dict['name']
                                print("Launching parted and sfdisk on " + partition_longdevname)
                                try:
                                    cmd_dict[("parted", partition_longdevname)] = subprocess.Popen(self._get_parted_cmd_list(partition_longdevname), env=env_C_locale, encoding="utf-8", universal_newlines=True)
                                    cmd_dict[("sfdisk", partition_longdevname)] = subprocess.Popen(self._get_sfdisk_cmd_list(partition_longdevname), env=env_C_locale, encoding="utf-8", universal_newlines=True)
                                except Exception:
                                    print("Could launch sfdisk or parted on " + partition_longdevname)
                        elif key[0] == "blkid" and retcode == 0:
                            blkid_dict = Blkid.parse_blkid_output(proc.stdout.read())
                        elif key[0] == "osprober" and retcode == 0:
                            os_prober_dict = OsProber.parse_os_prober_output(proc.stdout.read())
                        elif key[0] == "sfdisk" and retcode == 0 and proc.stdout is not None:
                            sfdisk_dict_dict[key[1]] = Sfdisk.parse_sfdisk_dump_output(proc.stdout.read())
                        elif key[0] == "parted" and retcode == 0 and proc.stdout is not None:
                            if proc.stderr is not None:
                                stderr = proc.stderr.read()
                                print("parted with key " + str(key) + " had stderr " + stderr)
                                if "unrecognized disk label" not in stderr:
                                    parted_dict_dict[key[1]] = Parted.parse_parted_output(proc.stdout.read())
                        else:
                            print("COULD NOT PROCESS process launched with key " + str(key) + " return code" + str(retcode))
                            if proc.stdout is not None:
                                print("stdout:" + proc.stdout.read())
                            if proc.stderr is not None:
                                print(" stderr:" + proc.stderr.read())
                    else:  # No process is done, wait a bit and check again.
                        time.sleep(0.1)
                        continue
        else:
            raise Exception("Invalid drive query mode")
        self.drive_state = CombinedDriveState.construct_combined_drive_state_dict(lsblk_json_dict, blkid_dict, os_prober_dict, parted_dict_dict, sfdisk_dict_dict)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.drive_state)

        drive_query_end_time = datetime.now()
        print("Drive query took: " + str((drive_query_end_time - drive_query_start_time)))
        GLib.idle_add(self.populate_drive_selection_table)

