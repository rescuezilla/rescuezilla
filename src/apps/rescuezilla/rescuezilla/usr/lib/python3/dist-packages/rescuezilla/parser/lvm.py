# ----------------------------------------------------------------------
#   Copyright (C) 1995-2005 Gentoo Foundation
#   Copyright (C) 2012 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2020 Shasheen Ediriweera (Rescuezilla.com) <rescuezilla@gmail.com>
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

import json
from os.path import isdir, isfile

import utility
from utility import Utility

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


# To maximize Rescuezilla's support for Clonezilla image format, this file is currently largely a Python port of
# Clonezilla's Logical Volume Manager handling.
#
# For further information, refer to [1], [2], and the save_logv() function of [3].
#
# [1] https://gitlab.com/stevenshiau/clonezilla/-/blob/master/sbin/ocs-lvm2-start
# [2] https://gitlab.com/stevenshiau/clonezilla/-/blob/master/sbin/ocs-lvm2-stop
# [3] https://gitlab.com/stevenshiau/clonezilla/-/blob/master/scripts/sbin/ocs-functions


class Lvm:
    def __init__(self):
        return

    # Clonezilla image format's "lvm_vg_dev.list" contains Volume Group (VG) information
    @staticmethod
    def parse_volume_group_device_list_string(lvm_vg_dev_list_string):
        volume_group_device_dict = {}
        for line in lvm_vg_dev_list_string.splitlines():
            component_list = line.split(" ")
            if len(component_list) == 3:
                key = component_list[0]
                volume_group_device_dict[key] = {}
                volume_group_device_dict[key]['device_node'] = component_list[1]
                volume_group_device_dict[key]['uuid'] = component_list[2]
            else:
                raise Exception("Unable to process: " + lvm_vg_dev_list_string)

        return volume_group_device_dict

    # Clonezilla image format's "lvm_logv.list" contains Logical Volume (LV) information
    @staticmethod
    def parse_logical_volume_device_list_string(lvm_logv_list_string):
        logical_volume_device_dict = {}
        for line in lvm_logv_list_string.split("\n"):
            # Yes, split on double space.
            split = line.split("  ", maxsplit=1)
            if len(split) > 1:
                key = split[0]
                logical_volume_device_dict[key] = {'metadata': split[1]}
        return logical_volume_device_dict

    @staticmethod
    def start_lvm2(logger):
        modinfo_process, modinfo_flat_command_string, modinfo_failed_message = Utility.run("Querying device-mapper kernel module (dm_mod).",
                                                           ["modinfo", "dm_mod"], use_c_locale=False, logger=logger)
        if modinfo_process.returncode != 0:
            modprobe_process, modprobe_flat_command_string, modprobe_failed_message = Utility.run("Loading device-mapper kernel module (dm_mod).",
                                                                ["modprobe", "dm_mod"], use_c_locale=False, logger=logger)
            if modprobe_process.returncode != 0:
                raise Exception(modprobe_failed_message)

        proc_misc_string = Utility.read_file_into_string("/proc/misc")
        if isdir("/proc/lvm") or "device-mapper" in proc_misc_string:
            vgscan_process, vgscan_flat_command_string, vgscan_failed_message = Utility.run("Search all volume groups (VGs)", ["vgscan"], use_c_locale=True, logger=logger)
            if vgscan_process.returncode == 0 or isfile("/etc/lvmtab") or isdir("/proc/lvm"):
                vgchange_process, vgchange_flat_command_string, vgchange_failed_message = Utility.run("Activate all logical volumes (LVs)",
                                                                    ["vgchange", "--activate", "y"], use_c_locale=False, logger=logger)
                if vgscan_process.returncode != 0:
                    raise Exception(vgchange_failed_message)
        return True

    @staticmethod
    def get_lvm_state_dict(logger):
        pvs_cmd_list = ["pvs", "-o", "pv_all,lv_all,vg_all", "--reportformat", "json"]
        pvs_process, flat_command_string, failed_message = Utility.run("LVM query", pvs_cmd_list, use_c_locale=True, logger=logger)
        return json.loads(pvs_process.stdout)

    @staticmethod
    def get_physical_volume_state_dict(logger):
        pvs_cmd_list = ["pvs", "-o", "pv_all", "--reportformat", "json"]
        pvs_process, flat_command_string, failed_message = Utility.run("Physical Volume (PV) query", pvs_cmd_list, use_c_locale=True, logger=logger)
        return json.loads(pvs_process.stdout)

    @staticmethod
    def get_volume_group_state_dict(logger):
        # Get volume group state with the physical volume information
        vgs_cmd_list = ["vgs", "-o", "vg_all,pv_all", "--reportformat", "json"]
        vgs_process, flat_command_string, failed_message = Utility.run("Volume Group (VG) query", vgs_cmd_list, use_c_locale=True, logger=logger)
        print(
            "Volume group query. return code: " + str(
                vgs_process.returncode) + " stdout: " + vgs_process.stdout + ". stderr=" + vgs_process.stderr)
        if vgs_process.returncode != 0:
            print("Non zero error code")
        return json.loads(vgs_process.stdout)

    @staticmethod
    def get_logical_volume_state_dict(logger):
        # Get logical volume state with the volume group information
        lvs_cmd_list = ["lvs", "-o", "lv_all,vg_all", "--reportformat", "json"]
        lvs_process, flat_command_string, failed_message = Utility.run("Logical Volume (LV) query", lvs_cmd_list, use_c_locale=True, logger=logger)
        return json.loads(lvs_process.stdout)

    @staticmethod
    def shutdown_lvm2(builder, logger):
        print("Shutting down the Logical Volume Manager (LVM)")
        # Using list here because its doesn't appear to be guaranteed that the keys are unique
        failed_lv_shutdown_list = []
        failed_vg_shutdown_list = []
        # Shutdown logical volumes
        lvs_dict = Lvm.get_logical_volume_state_dict(logger)
        print("Deactivating Logical Volumes (LVs)")
        if 'report' in lvs_dict.keys():
            for report in lvs_dict['report']:
                if 'lv' in report.keys():
                    for logical_volume_dict in report['lv']:
                        to_shutdown_lv = ""
                        if 'lv_path' in logical_volume_dict.keys():
                            to_shutdown_lv = logical_volume_dict['lv_path']
                        elif 'lv_name' in logical_volume_dict.keys():
                            to_shutdown_lv = logical_volume_dict['lv_name']
                        else:
                            GLib.idle_add(utility.ErrorMessageModalPopup.display_nonfatal_warning_message, builder,
                                          "Could not find LV path or name. Unexpected " + str(logical_volume_dict))
                            print("No lv path or name found. Unexpected.")
                            continue

                        is_unmounted, message = Utility.umount_warn_on_busy(to_shutdown_lv)
                        if not is_unmounted:
                            failed_lv_shutdown_list.append([to_shutdown_lv, message])
                        else:
                            lvchange_cmd_list = ["lvchange", "--activate", "n", "--ignorelockingfailure", "--partial",
                                                 to_shutdown_lv]
                            lvchange_process, flat_command_string, failed_message = Utility.run(
                                "Shutting down logical volume: " + to_shutdown_lv, lvchange_cmd_list, use_c_locale=True, logger=logger)
                            if lvchange_process.returncode != 0:
                                failed_lv_shutdown_list.append([to_shutdown_lv, failed_message])

        # Shutdown volume groups
        vgs_dict = Lvm.get_volume_group_state_dict(logger)
        print("Deactivating Volume Groups (VGs)")
        if 'report' in vgs_dict.keys():
            for report in vgs_dict['report']:
                if 'vg' in report.keys():
                    for volume_group_dict in report['vg']:
                        to_shutdown_vg = ""
                        if 'vg_path' in volume_group_dict.keys():
                            to_shutdown_vg = volume_group_dict['vg_path']
                        elif 'vg_name' in volume_group_dict.keys():
                            to_shutdown_vg = volume_group_dict['vg_name']
                        else:
                            GLib.idle_add(utility.ErrorMessageModalPopup.display_nonfatal_warning_message, builder,
                                          "Could not find VG path or name. Unexpected " + str(volume_group_dict))
                            print("No vg path or name found. Unexpected.")
                            continue
                        lv_count = int(volume_group_dict['lv_count'])
                        if lv_count != 0:
                            vgchange_cmd_list = ["vgchange", "--activate", "n", "--ignorelockingfailure", "--partial",
                                                 to_shutdown_vg]
                            vgchange_process, flat_command_string, failed_message = Utility.run(
                                "Shutting down volume group: " + to_shutdown_vg, vgchange_cmd_list, use_c_locale=True, logger=logger)
                            if vgchange_process.returncode != 0:
                                failed_vg_shutdown_list.append([to_shutdown_vg, failed_message])

        # Checking if volume groups shutdown correctly
        vgs_dict = Lvm.get_volume_group_state_dict(logger)
        print("Checking if all Volume Groups (VGs) were de-activated")
        if 'report' in vgs_dict.keys():
            for report in vgs_dict['report']:
                if 'vg' in report.keys():
                    for volume_group_dict in report['vg']:
                        if 'active' in volume_group_dict.keys() and volume_group_dict['active'] == "active":
                            print("Unable to shutdown: " + str(volume_group_dict))

        print("Finished Shutting down the Logical Volume Manager")
        return failed_lv_shutdown_list, failed_vg_shutdown_list
