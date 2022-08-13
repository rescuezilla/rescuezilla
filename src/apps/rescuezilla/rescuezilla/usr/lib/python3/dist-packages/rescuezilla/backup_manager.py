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
import glob
import os
import pprint
import shutil
import subprocess
import threading
import traceback
from datetime import datetime
from pathlib import Path
from time import sleep
import re

import gi
from gi.repository import Gtk, Gdk, GLib, GObject

from logger import Logger
from parser.combined_drive_state import CombinedDriveState
from parser.lvm import Lvm
from parser.partclone import Partclone
from parser.parted import Parted
from parser.proc_mdstat import ProcMdstat
from parser.sfdisk import Sfdisk
from parser.swappt import Swappt
from utility import ErrorMessageModalPopup, Utility, _

# Signals should automatically propogate to processes called with subprocess.run().
# TODO: This class uses 'subprocess.call', which provides exit code but not stdout/stderr. It would be
# TODO: VERY useful to display stdout/stderr when the exit code is non-zero, like the RestoreManager does.
class BackupManager:
    def __init__(self, builder, human_readable_version):
        self.backup_in_progress_lock = threading.Lock()
        self.backup_in_progress = False
        self.builder = builder
        self.human_readable_version = human_readable_version
        self.backup_progress = self.builder.get_object("backup_progress")
        self.backup_progress_status = self.builder.get_object("backup_progress_status")
        self.main_statusbar = self.builder.get_object("main_statusbar")
        # proc dictionary
        self.proc = collections.OrderedDict()
        self.logger = None

        self.requested_stop = False

    def is_backup_in_progress(self):
        with self.backup_in_progress_lock:
            return self.backup_in_progress

    def start_backup(self,
                     selected_drive_key,
                     partitions_to_backup,
                     drive_state,
                     dest_dir,
                     backup_notes,
                     compression_dict,
                     is_rescue,
                     completed_backup_callback,
                     metadata_only_image_to_annotate=None,
                     on_separate_thread=True):
        self.backup_timestart = datetime.now()
        self.completed_backup_callback = completed_backup_callback
        self.selected_drive_key = selected_drive_key
        self.dest_dir = dest_dir
        self.backup_notes = backup_notes
        self.compression_dict = compression_dict
        self.is_rescue = is_rescue
        self.partitions_to_backup = partitions_to_backup
        # Entire machine's drive state
        # TODO: This is a crutch that ideally will be removed. It's very bad from an abstraction perspective, and
        # TODO: clear abstractions is important for ensuring correctness of the backup/restore operation
        self.drive_state = drive_state
        GLib.idle_add(self.update_backup_progress_bar, 0)
        with self.backup_in_progress_lock:
            self.backup_in_progress = True
        self.metadata_only_image_to_annotate = metadata_only_image_to_annotate
        self.is_cloning = False
        if self.metadata_only_image_to_annotate is not None:
            self.is_cloning = True
        else:
            self.is_cloning = False
        if on_separate_thread:
            thread = threading.Thread(target=self.do_backup_wrapper)
            thread.daemon = True
            thread.start()
        else:
            return self.do_backup()

    # Intended to be called via event thread
    # Sending signals to process objects on its own thread. Relying on Python GIL.
    # TODO: Threading practices here need overhaul. Use threading.Lock() instead of GIL
    def cancel_backup(self):
        # Again, relying on GIL.
        self.requested_stop = True
        if len(self.proc) == 0:
            self.logger.write("Nothing to cancel")
        else:
            self.logger.write("Will send cancel signal to " + str(len(self.proc)) + " processes.")
            for key in self.proc.keys():
                process = self.proc[key]
                try:
                    self.logger.write("Sending SIGTERM to " + str(process))
                    # Send SIGTERM
                    process.terminate()
                except:
                    self.logger.write("Error killing process. (Maybe already dead?)")
        with self.backup_in_progress_lock:
            self.backup_in_progress = False
        if not self.is_cloning:
            self.completed_backup(False, _("Operation cancelled by user."))

    def do_backup_wrapper(self):
        try:
            self.do_backup()
        except Exception as exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            GLib.idle_add(self.completed_backup, False, _("Error creating backup: ") + tb)
            return

    def do_backup(self):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.partitions_to_backup)
        self.at_least_one_non_fatal_error = False
        self.requested_stop = False
        # Clear proc dictionary
        self.proc.clear()
        self.summary_message_lock = threading.Lock()
        self.summary_message = ""

        if self.is_rescue and not self.is_cloning:
            with self.summary_message_lock:
                self.summary_message += _("Rescue option is enabled.") + "\n"

        env = Utility.get_env_C_locale()

        print("mkdir " + self.dest_dir)
        os.mkdir(self.dest_dir)

        short_selected_device_node = re.sub('/dev/', '', self.selected_drive_key)
        enduser_date = datetime.today().strftime('%Y-%m-%d-%H%M')
        clonezilla_img_filepath = os.path.join(self.dest_dir, "clonezilla-img")
        with open(clonezilla_img_filepath, 'w') as filehandle:
            try:
                output = "This image was saved by Rescuezilla at " + enduser_date + "\nSaved by " + self.human_readable_version + "\nThe log during saving:\n----------------------------------------------------------\n\n"
                filehandle.write(output)
            except:
                tb = traceback.format_exc()
                traceback.print_exc()
                error_message = _("Failed to write destination file. Please confirm it is valid to create the provided file path, and try again.") + "\n\n" + tb
                GLib.idle_add(self.completed_backup, False, error_message)
                return False, error_message

        self.logger = Logger(clonezilla_img_filepath)

        # Backup RAID information (Clonezilla's dump_software_raid_info_if_exists function)
        original_proc_mdstat_filepath = "/proc/mdstat"
        if os.path.isfile(original_proc_mdstat_filepath):
            proc_mdstat_string = Utility.read_file_into_string(original_proc_mdstat_filepath)
            proc_mdstat_dict = ProcMdstat.parse_proc_mdstat_string(proc_mdstat_string)
            if len(proc_mdstat_dict.keys()) > 0:
                # Copy the mdstat file to the destination disk, as CLonezilla
                copied_proc_mdstat_filepath = os.path.join(self.dest_dir, "mdstat.txt")
                GLib.idle_add(self.display_status, _("Saving: {file}").format(file=copied_proc_mdstat_filepath), "")
                with open(copied_proc_mdstat_filepath, 'w') as filehandle:
                    filehandle.write(proc_mdstat_string)
                    filehandle.flush()
                # Save mdadm.conf
                mdadm_conf_filepath = os.path.join(self.dest_dir, "mdadm.conf")
                GLib.idle_add(self.display_status, _("Saving: {file}").format(file=mdadm_conf_filepath), "")
                process, flat_command_string, failed_message = Utility.run("Saving mdadm.conf", ["mdadm", "--detail", "--scan"],
                                                                               use_c_locale=True,
                                                                               output_filepath=mdadm_conf_filepath,
                                                                               logger=self.logger)
                if process.returncode != 0:
                    # Clonezilla doesn't handle non-zero return code, so to maximize compatibility Rescuezilla doesn't
                    # either
                    GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)
                # Export details for each RAID device
                for raid_dev_key in proc_mdstat_dict.keys():
                    raid_device_query_filepath = os.path.join(self.dest_dir, raid_dev_key + ".txt")
                    GLib.idle_add(self.display_status, _("Saving: {file}").format(file=raid_device_query_filepath), "")
                    process, flat_command_string, failed_message = Utility.run("Saving " + raid_device_query_filepath,
                                                                               ["mdadm", "--query", "--detail", "--export", "/dev/" + raid_dev_key],
                                                                               use_c_locale=True,
                                                                               output_filepath=raid_device_query_filepath,
                                                                               logger=self.logger)
                    if process.returncode != 0:
                        # Clonezilla doesn't handle non-zero return code, so to maximize compatibility Rescuezilla
                        # doesn't either
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                      failed_message)

        if not self.is_cloning:
            backup_notes_filepath = os.path.join(self.dest_dir, "rescuezilla.description.txt")
            if self.backup_notes.strip() != "":
                self.logger.write("Writing backup description file to " + backup_notes_filepath)
                GLib.idle_add(self.display_status, _("Saving: {file}").format(file=backup_notes_filepath), "")
                with open(backup_notes_filepath, 'w') as filehandle:
                    filehandle.write(self.backup_notes)
                    filehandle.flush()

            blkdev_list_filepath = os.path.join(self.dest_dir, "blkdev.list")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=blkdev_list_filepath), "")
            process, flat_command_string, failed_message = Utility.run("Saving blkdev.list", ["lsblk", "-oKNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL", self.selected_drive_key], use_c_locale=True, output_filepath=blkdev_list_filepath, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            blkid_list_filepath = os.path.join(self.dest_dir, "blkid.list")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=blkid_list_filepath), "")
            blkid_cmd_list = ["blkid"]
            sort_cmd_list = ["sort", "-V"]
            Utility.print_cli_friendly("blkid ", [blkid_cmd_list, sort_cmd_list])
            process, flat_command_string, failed_message = Utility.run("Saving blkid.list", ["blkid"], use_c_locale=True, output_filepath=blkid_list_filepath, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message



            info_lshw_filepath = os.path.join(self.dest_dir, "Info-lshw.txt")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=info_lshw_filepath), "")
            process, flat_command_string, failed_message = Utility.run("Saving Info-lshw.txt", ["lshw"], use_c_locale=True, output_filepath=info_lshw_filepath, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            info_dmi_txt_filepath = os.path.join(self.dest_dir, "Info-dmi.txt")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=info_dmi_txt_filepath), "")
            with open(info_dmi_txt_filepath, 'w') as filehandle:
                filehandle.write("# This image was saved from this machine with DMI info at " + enduser_date + ":\n")
                filehandle.flush()
            process, flat_command_string, failed_message = Utility.run("Saving Info-dmi.txt", ["dmidecode"], use_c_locale=True, output_filepath=info_dmi_txt_filepath, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            info_lspci_filepath = os.path.join(self.dest_dir, "Info-lspci.txt")
            with open(info_lspci_filepath, 'w') as filehandle:
                # TODO: Improve datetime format string.
                filehandle.write("This image was saved from this machine with PCI info at " + enduser_date + "\n")
                filehandle.write("'lspci' results:\n")
                filehandle.flush()

            process, flat_command_string, failed_message = Utility.run("Appending `lspci` output to Info-lspci.txt", ["lspci"], use_c_locale=True, output_filepath=info_lspci_filepath, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            msg_delimiter_star_line = "*****************************************************."
            with open(info_lspci_filepath, 'a+') as filehandle:
                filehandle.write(msg_delimiter_star_line + "\n")
                filehandle.write("'lspci -n' results:\n")
                filehandle.flush()

            # Show PCI vendor and device codes as numbers instead of looking them up in the PCI ID list.
            process, flat_command_string, failed_message = Utility.run("Appending `lspci -n` output to Info-lspci.txt", ["lspci", "-n"], use_c_locale=True, output_filepath=info_lspci_filepath, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            info_smart_filepath = os.path.join(self.dest_dir, "Info-smart.txt")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=info_smart_filepath), "")
            with open(info_smart_filepath, 'w') as filehandle:
                filehandle.write("This image was saved from this machine with hard drive S.M.A.R.T. info at " + enduser_date + "\n")
                filehandle.write(msg_delimiter_star_line + "\n")
                filehandle.write("For the drive: " + self.selected_drive_key + "\n")
                filehandle.flush()

            # VirtualBox doesn't support smart, so ignoring the exit code here.
            # FIXME: Improve this.
            process, flat_command_string, failed_message = Utility.run("Saving Info-smart.txt", ["smartctl", "--all", self.selected_drive_key], use_c_locale=True, output_filepath=info_smart_filepath, logger=self.logger)

            info_os_prober_filepath = os.path.join(self.dest_dir, "Info-OS-prober.txt")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=info_os_prober_filepath), "")
            with open(info_os_prober_filepath, 'w') as filehandle:
                filehandle.write("This OS-related info was saved from this machine with os-prober at " + enduser_date + "\n")
                filehandle.flush()
            process, flat_command_string, failed_message = Utility.run("Running os-prober and appending output to Info-OS-prober.txt",
                                                                           ["os-prober"],
                                                                           use_c_locale=True,
                                                                           output_filepath=info_os_prober_filepath,
                                                                           logger=self.logger)
            if process.returncode != 0:
                self.logger.write(failed_message)
                # Not considering os-prober exit code as fatal, to match Clonezilla's behavior

            with open(info_os_prober_filepath, 'a+') as filehandle:
                filehandle.write(msg_delimiter_star_line + "\n")
                filehandle.write("This Linux boot related info was saved from this machine with linux-boot-prober at " + enduser_date + "\n")
                filehandle.flush()

            for partition_key in self.partitions_to_backup:
                process, flat_command_string, failed_message = Utility.run("Running linux-boot-prober for " + partition_key,
                                                                           ["linux-boot-prober", partition_key],
                                                                           use_c_locale=True,
                                                                           output_filepath=info_os_prober_filepath,
                                                                           logger=self.logger)
                if process.returncode != 0:
                    self.logger.write(failed_message)
                    # Not considering os-prober exit code as fatal, to match Clonezilla's behavior

            filepath = os.path.join(self.dest_dir, "Info-packages.txt")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
            # Save Debian package informtion
            if shutil.which("dpkg") is not None:
                rescuezilla_package_list = ["rescuezilla", "partclone", "util-linux", "gdisk"]
                with open(filepath, 'w') as filehandle:
                    filehandle.write("Image was saved by these Rescuezilla-related packages:\n ")
                    for pkg in rescuezilla_package_list:
                        dpkg_process = subprocess.run(['dpkg', "--status", pkg], capture_output=True, encoding="UTF-8")
                        if dpkg_process.returncode != 0:
                            continue
                        for line in dpkg_process.stdout.split("\n"):
                            if re.search("^Version: ", line):
                                version = line[len("Version: "):]
                                filehandle.write(pkg + "-" + version + " ")
                    filehandle.write("\nSaved by " + self.human_readable_version + ".\n")

        # TODO: Clonezilla creates a file named "Info-saved-by-cmd.txt" file, to allow users to re-run the exact
        #  command again without going through the wizard. The proposed Rescuezilla approach to this feature is
        #  discussed here: https://github.com/rescuezilla/rescuezilla/issues/106

        filepath = os.path.join(self.dest_dir, "parts")
        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
        with open(filepath, 'w') as filehandle:
            i = 0
            for partition_key in self.partitions_to_backup:
                short_partition_key = re.sub('/dev/', '', partition_key)
                to_backup_dict = self.partitions_to_backup[partition_key]
                is_swap = False
                if 'filesystem' in to_backup_dict.keys() and to_backup_dict['filesystem'] == "swap":
                    is_swap = True
                if 'type' not in to_backup_dict.keys() or 'type' in to_backup_dict.keys() and 'extended' != to_backup_dict['type'] and not is_swap:
                    # Clonezilla does not write the extended partition node into the parts file,
                    # nor does it write swap partition node
                    filehandle.write('%s' % short_partition_key)
                    # Ensure no trailing space on final iteration (to match Clonezilla format exactly)
                    if i + 1 != len(self.partitions_to_backup.keys()):
                        filehandle.write(' ')
                i += 1
            # FIXME: This diverges from Clonezilla behavior. It's possible for Rescuezilla to write just a newline for
            # FIXME: eg, disk full of only swap partitions. Rescuezilla can handle restoring such images, but Clonezilla
            # FIXME: cannot (a divergence of behavior).
            filehandle.write('\n')

        filepath = os.path.join(self.dest_dir, "disk")
        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
        with open(filepath, 'w') as filehandle:
            filehandle.write('%s\n' % short_selected_device_node)

        compact_parted_filepath = os.path.join(self.dest_dir, short_selected_device_node + "-pt.parted.compact")
        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=compact_parted_filepath), "")
        # Parted drive information with human-readable "compact" units: KB/MB/GB rather than sectors.
        process, flat_command_string, failed_message = Utility.run("Saving " + compact_parted_filepath, ["parted", "--script", self.selected_drive_key, "unit", "compact", "print"], use_c_locale=True, output_filepath=compact_parted_filepath, logger=self.logger)
        if process.returncode != 0:
            # Human-readable compact units is not that important.
            print(failed_message)
            if not self.is_cloning:
                GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)

        # Parted drive information with standard sector units. Clonezilla doesn't output easily parsable output using
        # the --machine flag, so for maximum Clonezilla compatibility neither does Rescuezilla.
        parted_filepath = os.path.join(self.dest_dir, short_selected_device_node + "-pt.parted")
        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=parted_filepath), "")
        parted_process, flat_command_string, failed_message = Utility.run("Saving " + parted_filepath,
                                                          ["parted", "--script", self.selected_drive_key, "unit", "s",
                                                           "print"], use_c_locale=True, output_filepath=parted_filepath, logger=self.logger)
        if process.returncode != 0:
            print(failed_message)
            # Clonezilla doesn't consider non-zero parted return code as fatal. Indeed, RAID md devices without a
            # partition table returns an error using parted but Clonezilla is happy to continue. Rescuezilla does the
            # same (but displays the error to the user). For cloning, the not displaying any error message is fine.
            if not self.is_cloning:
               with self.summary_message_lock:
                    self.summary_message += failed_message
               GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)

        if os.path.isdir("/sys/firmware/efi/efivars"):
            # Save EFI NVRAM info. What we need is actually the label
            efi_nvram_filepath = os.path.join(self.dest_dir, "efi-nvram.dat")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=efi_nvram_filepath), "")
            process, flat_command_string, failed_message = Utility.run("Saving EFI NVRAM info",
                                                                              ["efibootmgr", "--verbose"],
                                                                              use_c_locale=True,
                                                                              output_filepath=efi_nvram_filepath,
                                                                              logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message
            if self.is_cloning:
                self.metadata_only_image_to_annotate.efi_nvram_dat_absolute_path = efi_nvram_filepath

        parted_dict = Parted.parse_parted_output(parted_process.stdout)
        partition_table = parted_dict['partition_table']

        # Save MBR for both msdos and GPT disks
        if "gpt" == partition_table or "msdos" == partition_table:
            filepath = os.path.join(self.dest_dir, short_selected_device_node + "-mbr")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
            process, flat_command_string, failed_message = Utility.run("Saving " + filepath,
                                                       ["dd", "if=" + self.selected_drive_key, "of=" + filepath,
                                                        "bs=512", "count=1"], use_c_locale=False, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message
            if self.is_cloning:
                self.metadata_only_image_to_annotate._mbr_absolute_path = filepath

        if "gpt" == partition_table and not self.is_cloning:
            first_gpt_filename = short_selected_device_node + "-gpt-1st"
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=first_gpt_filename), "")
            dd_process, flat_command_string, failed_message = Utility.run("Saving " + first_gpt_filename,
                                                          ["dd", "if=" + self.selected_drive_key, "of=" + os.path.join(self.dest_dir, first_gpt_filename),
                                                           "bs=512", "count=34"], use_c_locale=False, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            # From Clonezilla's scripts/sbin/ocs-functions:
            # We need to get the total size of disk so that we can skip and dump the last block:
            # The output of 'parted -s /dev/sda unit s print' is like:
            # --------------------
            # Disk /dev/hda: 16777215s
            # Sector size (logical/physical): 512B/512B
            # Partition Table: gpt
            #
            # Number  Start     End        Size       File system  Name     Flags
            #  1      34s       409640s    409607s    fat32        primary  msftres
            #  2      409641s   4316406s   3906766s   ext2         primary
            #  3      4316407s  15625000s  11308594s  reiserfs     primary
            # --------------------
            # to_seek = "$((${src_disk_size_sec}-33+1))"
            to_skip = parted_dict['capacity'] - 32
            second_gpt_filename = short_selected_device_node + "-gpt-2nd"
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=second_gpt_filename), "")
            process, flat_command_string, failed_message = Utility.run("Saving " + second_gpt_filename,
                                                       ["dd", "if=" + self.selected_drive_key, "of=" + os.path.join(self.dest_dir, second_gpt_filename),
                                                        "skip=" + str(to_skip),
                                                        "bs=512", "count=33"], use_c_locale=False, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            # LC_ALL=C sgdisk -b $target_dir_fullpath/$(to_filename ${ihd})-gpt.gdisk /dev/$ihd | tee --append ${OCS_LOGFILE}
            gdisk_filename = short_selected_device_node + "-gpt.gdisk"
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=gdisk_filename), "")
            process, flat_command_string, failed_message = Utility.run("Saving " + gdisk_filename,
                                                       ["sgdisk", "--backup", os.path.join(self.dest_dir, gdisk_filename), self.selected_drive_key], use_c_locale=True, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            sgdisk_filename = short_selected_device_node + "-gpt.sgdisk"
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=sgdisk_filename), "")
            process, flat_command_string, failed_message = Utility.run("Saving " + sgdisk_filename, ["sgdisk", "--print", self.selected_drive_key], use_c_locale=True, output_filepath=os.path.join(self.dest_dir, sgdisk_filename), logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message
        elif "msdos" == partition_table:
            # image_save
            first_partition_key, first_partition_offset_bytes = CombinedDriveState.get_first_partition(
                self.partitions_to_backup)
            # Maximum hidden data to backup is 1024MB
            hidden_data_after_mbr_limit = 1024 * 1024 * 1024
            self.logger.write("Detected first partition is " + first_partition_key + " at byte offset " + str(first_partition_offset_bytes) + "\n")
            if first_partition_offset_bytes > hidden_data_after_mbr_limit:
                # If the post-mbr gap is too large, Clonezilla does not backup the data but instead creates a notes file
                # FIXME: Rescuezilla doesn't yet match Clonezilla's ability to re-install GRUB, so it makes sense to
                # FIXME: continue to backup a post-mbr gap until full parity with Clonezilla is achieved.
                post_mbr_gap_sector_count = 2047
                self.logger.write("Calculated very large hidden data after MBR size, so copying minimal post-MBR gap")
                not_creating_hidden_data_info_filepath = os.path.join(self.dest_dir, short_selected_device_node + "-hidden-data-after-mbr.notes.txt")
                GLib.idle_add(self.display_status, _("Saving: {file}").format(file=not_creating_hidden_data_info_filepath))
                with open(not_creating_hidden_data_info_filepath, 'w') as filehandle:
                    try:
                        output = "The hidden data space size (" + str(first_partition_offset_bytes) + " bytes) is larger than the " + str(hidden_data_after_mbr_limit) + " byte limit. Copying minimal post-MBR gap.\n"
                        filehandle.write(output)
                    except:
                        tb = traceback.format_exc()
                        traceback.print_exc()
                        error_message = _(
                            "Failed to write hidden data info file. Please confirm it is valid to create the provided file path, and try again.") + "\n\n" + tb
                        GLib.idle_add(self.completed_backup, False, error_message)
                        return False, failed_message

            else:
                first_partition_offset_sectors = int(first_partition_offset_bytes / 512)
                post_mbr_gap_sector_count = first_partition_offset_sectors - 1

            hidden_mbr_data_filepath =  os.path.join(self.dest_dir, short_selected_device_node + "-hidden-data-after-mbr")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=hidden_mbr_data_filepath), "")
            process, flat_command_string, failed_message = Utility.run("Saving " + hidden_mbr_data_filepath,
                                                       ["dd", "if=" + self.selected_drive_key, "of=" + hidden_mbr_data_filepath,
                                                        "skip=1", "bs=512",
                                                        "count=" + str(post_mbr_gap_sector_count)], use_c_locale=False, logger=self.logger)
            if process.returncode != 0:
                with self.summary_message_lock:
                    self.summary_message += failed_message
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message
            if self.is_cloning:
                self.metadata_only_image_to_annotate.post_mbr_gap_dict['absolute_path'] = hidden_mbr_data_filepath

        else:
            self.logger.write("Partition table is: " + partition_table)

        # Parted sees drives with direct filesystem applied as loop partition table.
        if partition_table is not None and partition_table != "loop":
            sfdisk_filepath = os.path.join(self.dest_dir, short_selected_device_node + "-pt.sf")
            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=sfdisk_filepath), "")
            process, flat_command_string, failed_message = Utility.run("Saving " + sfdisk_filepath, ["sfdisk", "--dump", self.selected_drive_key], output_filepath=sfdisk_filepath, use_c_locale=True, logger=self.logger)
            if process.returncode != 0:
                print(failed_message)
                if not self.is_cloning:
                    with self.summary_message_lock:
                        self.summary_message += failed_message
                    # Matches Clonezilla by not considering sfdisk failure as fatal.
                    GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)

        filepath = os.path.join(self.dest_dir, short_selected_device_node + "-chs.sf")
        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
        process, flat_command_string, failed_message = Utility.run("Retreiving disk geometry with sfdisk ", ["sfdisk", "--show-geometry", self.selected_drive_key], use_c_locale=True, logger=self.logger)
        if process.returncode != 0:
            self.logger.write(failed_message)
            with self.summary_message_lock:
                self.summary_message += "Failed to retrieve disk geometry for " + self.selected_drive_key + "."
            GLib.idle_add(self.completed_backup, False, failed_message)
            return False, failed_message
        else:
            geometry_dict = Sfdisk.parse_sfdisk_show_geometry(process.stdout)
            with open(filepath, 'w') as filehandle:
                for key in geometry_dict.keys():
                    output = key + "=" + str(geometry_dict[key])
                    self.logger.write(output)
                    filehandle.write('%s\n' % output)
            if self.is_cloning:
                self.metadata_only_image_to_annotate.sfdisk_chs_dict = geometry_dict

        if not self.is_cloning:
            # Query all Physical Volumes (PV), Volume Group (VG) and Logical Volume (LV). See unit test for a worked example.
            # TODO: In the Rescuezilla application architecture, this LVM information is best extracted during the drive
            # TODO: query step, and then integrated into the "combined drive state" dictionary. Doing it during the backup
            # TODO: process matches how Clonezilla does it, which is sufficient for now.
            # FIXME: This section is duplicated in partitions_to_restore.py.
            # Start the Logical Volume Manager (LVM). Caller raises Exception on failure
            Lvm.start_lvm2(self.logger)
            relevant_vg_name_dict = {}
            vg_state_dict = Lvm.get_volume_group_state_dict(self.logger)
            for partition_key in list(self.partitions_to_backup.keys()):
                for report_dict in vg_state_dict['report']:
                    for vg_dict in report_dict['vg']:
                        if 'pv_name' in vg_dict.keys() and (partition_key == vg_dict['pv_name']
                                                            or self.selected_drive_key == vg_dict['pv_name']):
                            if 'vg_name' in vg_dict.keys():
                                vg_name = vg_dict['vg_name']
                            else:
                                GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                              "Could not find volume group name vg_name in " + str(vg_dict))
                                # TODO: Re-evaluate how exactly Clonezilla uses /NOT_FOUND and whether introducing it here
                                # TODO: could improve Rescuezilla/Clonezilla interoperability.
                                continue
                            if 'pv_uuid' in vg_dict.keys():
                                pv_uuid = vg_dict['pv_uuid']
                            else:
                                GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                              "Could not find physical volume UUID pv_uuid in " + str(vg_dict))
                                continue
                            relevant_vg_name_dict[vg_name] = partition_key
                            lvm_vg_dev_list_filepath = os.path.join(self.dest_dir, "lvm_vg_dev.list")
                            GLib.idle_add(self.display_status, _("Saving: {file}").format(file=lvm_vg_dev_list_filepath), "")
                            with open(lvm_vg_dev_list_filepath, 'a+') as filehandle:
                                if partition_key == vg_dict['pv_name']:
                                   filehandle.write(vg_name + " " + partition_key + " " + pv_uuid + "\n")
                                elif self.selected_drive_key == vg_dict['pv_name']:
                                   filehandle.write(vg_name + " " + self.selected_drive_key + " " + pv_uuid + "\n")

            lv_state_dict = Lvm.get_logical_volume_state_dict(self.logger)
            for report_dict in lv_state_dict['report']:
                for lv_dict in report_dict['lv']:
                    # Only consider VGs that match the partitions to backup list
                    if 'vg_name' in lv_dict.keys() and lv_dict['vg_name'] in relevant_vg_name_dict.keys():
                        vg_name = lv_dict['vg_name']
                        if 'lv_path' in lv_dict.keys():
                            lv_path = lv_dict['lv_path']
                        else:
                            GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                          "Could not find lv_path name in " + str(lv_dict))
                            continue
                        file_command_process, flat_command_string, failed_message = Utility.run("logical volume file info",
                                                                                ["file", "--dereference",
                                                                                 "--special-files", lv_path], use_c_locale=True, logger=self.logger)
                        if file_command_process.returncode != 0:
                            with self.summary_message_lock:
                                self.summary_message += failed_message
                            GLib.idle_add(self.completed_backup, False, failed_message)
                            return False, failed_message

                        output = file_command_process.stdout.split(" ", maxsplit=1)[1].strip()
                        lvm_logv_list_filepath = os.path.join(self.dest_dir, "lvm_logv.list")
                        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=lvm_logv_list_filepath), "")
                        # Append to file
                        with open(lvm_logv_list_filepath, 'a+') as filehandle:
                            filehandle.write(lv_path + "  " + output + "\n")

                        if 'lv_dm_path' in lv_dict.keys():
                            # Device mapper path, eg /dev/mapper/vgtest-lvtest
                            lv_dm_path = lv_dict['lv_dm_path']
                        else:
                            failed_message = "Could not find lv_dm_path name in " + str(lv_dict)
                            GLib.idle_add(self.completed_backup, False, failed_message)
                            return False, failed_message

                        if lv_dm_path in self.drive_state.keys() and 'partitions' in self.drive_state[lv_dm_path].keys():
                            # Remove the partition key associated with the volume group that contains this LVM logical volume
                            # eg, /dev/sdc1 with detected filesystem, and replace it with  the logical volume filesystem.
                            # In other words, don't backup both the /dev/sdc1 device node AND the /dev/mapper node.
                            long_partition_key = relevant_vg_name_dict[lv_dict['vg_name']]
                            self.partitions_to_backup.pop(long_partition_key, None)
                            for logical_volume in self.drive_state[lv_dm_path]['partitions'].keys():
                                # Use the system drive state to get the exact filesystem for this /dev/mapper/ node,
                                # as derived from multiple sources (parted, lsblk etc) like how Clonezilla does it.
                                self.partitions_to_backup[lv_path] = self.drive_state[lv_dm_path]['partitions'][logical_volume]
                                self.partitions_to_backup[lv_path]['type'] = 'part'

                        lvm_vgname_filepath = os.path.join(self.dest_dir, "lvm_" + vg_name + ".conf")
                        # TODO: Evaluate the Clonezilla message from 2013 message that this command won't work on NFS
                        # TODO: due to a vgcfgbackup file lock issue.
                        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=lvm_vgname_filepath), "")
                        vgcfgbackup_process, flat_command_string, failed_message = Utility.run("Saving LVM VG config " + lvm_vgname_filepath,
                                                                               ["vgcfgbackup", "--file",
                                                                                lvm_vgname_filepath, vg_name], use_c_locale=True, logger=self.logger)
                        if vgcfgbackup_process.returncode != 0:
                            with self.summary_message_lock:
                                self.summary_message += failed_message
                            GLib.idle_add(self.completed_backup, False, failed_message)
                            return False, failed_message

        filepath = os.path.join(self.dest_dir, "dev-fs.list")
        GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
        with open(filepath, 'w') as filehandle:
            filehandle.write('# <Device name>   <File system>\n')
            filehandle.write(
                '# The file systems detected below are a combination of several sources. The values may differ from `blkid` and `parted`.\n')
            for partition_key in self.partitions_to_backup.keys():
                filesystem = self.partitions_to_backup[partition_key]['filesystem']
                filehandle.write('%s %s\n' % (partition_key, filesystem))

        # Determine the size of each partition, and the total size. This is used for the weighted progress bar
        total_size = 0
        for partition_key in self.partitions_to_backup.keys():
            size = self.partitions_to_backup[partition_key]['size']
            self.partitions_to_backup[partition_key]['cumulative_bytes'] = total_size
            total_size += size

        partition_number = 0
        for partition_key in self.partitions_to_backup.keys():
            GLib.idle_add(self.display_status, "", "")
            partition_number += 1
            total_progress_float = Utility.calculate_progress_ratio(current_partition_completed_percentage=0,
                                                                    current_partition_bytes=self.partitions_to_backup[partition_key]['size'],
                                                                    cumulative_bytes=self.partitions_to_backup[partition_key]['cumulative_bytes'],
                                                                    total_bytes=total_size,
                                                                    image_number=partition_number,
                                                                    num_partitions=len(self.partitions_to_backup))
            GLib.idle_add(self.update_backup_progress_bar, total_progress_float)
            is_unmounted, message = Utility.umount_warn_on_busy(partition_key)
            if not is_unmounted:
                self.logger.write(message)
                with self.summary_message_lock:
                    self.summary_message += message + "\n"
                GLib.idle_add(self.completed_backup, False, message)

            short_device_node = re.sub('/dev/', '', partition_key)
            short_device_node = re.sub('/', '-', short_device_node)
            filesystem = self.partitions_to_backup[partition_key]['filesystem']

            if 'type' in self.partitions_to_backup[partition_key].keys() and 'extended' in \
                    self.partitions_to_backup[partition_key]['type']:
                self.logger.write("Detected " + partition_key + " as extended partition. Backing up EBR")
                filepath = os.path.join(self.dest_dir, short_device_node + "-ebr")
                GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
                process, flat_command_string, failed_message = Utility.run("Saving " + filepath,
                                                           ["dd", "if=" + partition_key, "of=" + filepath, "bs=512",
                                                            "count=1"], use_c_locale=False, logger=self.logger)
                if process.returncode != 0:
                    with self.summary_message_lock:
                        self.summary_message += failed_message
                    GLib.idle_add(self.completed_backup, False, failed_message)
                    return False, failed_message

                # TODO: Handle exit code
                if self.is_cloning:
                    self.metadata_only_image_to_annotate.ebr_dict = {'short_device_node': short_device_node,
                                                                     'absolute_path': filepath}
                continue

            if filesystem == 'swap':
                filepath = os.path.join(self.dest_dir, "swappt-" + short_device_node + ".info")
                GLib.idle_add(self.display_status, _("Saving: {file}").format(file=filepath), "")
                with open(filepath, 'w') as filehandle:
                    uuid = ""
                    label = ""
                    if 'uuid' in self.partitions_to_backup[partition_key].keys():
                        uuid = self.partitions_to_backup[partition_key]['uuid']
                    if 'label' in self.partitions_to_backup[partition_key].keys():
                        label = self.partitions_to_backup[partition_key]['label']
                    filehandle.write('UUID="%s"\n' % uuid)
                    filehandle.write('LABEL="%s"\n' % label)
                    with self.summary_message_lock:
                        self.summary_message += _("Successful backup of swap partition {partition_name}").format(
                            partition_name=partition_key) + "\n"
                    if self.is_cloning:
                        self.metadata_only_image_to_annotate.image_format_dict_dict[short_device_node] = Swappt.parse_swappt_info(
                            Utility.read_file_into_string(filepath))
                        self.metadata_only_image_to_annotate.image_format_dict_dict[short_device_node]['type'] = "swap"
                        self.metadata_only_image_to_annotate.image_format_dict_dict[short_device_node]['prefix'] = short_device_node
                        self.metadata_only_image_to_annotate.image_format_dict_dict[short_device_node]['is_lvm_logical_volume'] = False
                continue

            if filesystem == "ntfs":
                GLib.idle_add(self.display_status, _("Running {app} on {device}").format(app="ntfsfix", device=partition_key), "")
                is_success, failed_message = Utility.run_ntfsfix(partition_key)
                if not is_success:
                    self.logger.write(failed_message + "\n")
                    GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)
                    with self.summary_message_lock:
                        self.summary_message += failed_message + "\n"

                # Create Clonezilla's NTFS boot reserved partition "sda1.info"
                tmp_mount = "/tmp/rescuezilla.ntfs.mount"
                if self.is_partition_windows_boot_reserved(partition_key, tmp_mount):
                    partition_info_filepath = os.path.join(self.dest_dir, short_device_node + ".info")
                    GLib.idle_add(self.display_status, _("Saving: {file}").format(file=partition_info_filepath), "")
                    self.logger.write("Detected partition " + partition_key + " is a Windows NTFS boot reserved partition. Writing " + partition_info_filepath)
                    with open(partition_info_filepath, 'w') as filehandle:
                        try:
                            output = "PARTITION_TYPE=Win_boot_reserved\n"
                            filehandle.write(output)
                        except:
                            tb = traceback.format_exc()
                            traceback.print_exc()
                            error_message = _(
                                "Failed to write NTFS boot reserve file. Please confirm it is valid to create the provided file path, and try again.") + "\n\n" + tb
                            GLib.idle_add(self.completed_backup, False, error_message)
                            return False, error_message

            # Clonezilla uses -q2 priority by default (partclone > partimage > dd).
            # PartImage does not appear to be maintained software, so for simplicity, Rescuezilla is using a
            # partclone > partclone.dd priority
            # [1] https://clonezilla.org/clonezilla-live/doc/01_Save_disk_image/advanced/09-advanced-param.php

            # TODO: Simplify logic
            compression_format = self.compression_dict['format']
            compression_suffix = Utility.get_compression_suffix(compression_format)
            compression_cmd_list = Utility.get_compression_cmd_list(compression_format, self.compression_dict['level'])

            split_size = "4GB"
            # Partclone dd blocksize (16MB)
            partclone_dd_bs = "16777216"
            filepath = ""
            # TODO: Re-enable APFS support -- currently partclone Apple Filesystem is not used because it's too unstable [1]
            # [1] https://github.com/rescuezilla/rescuezilla/issues/65
            if shutil.which("partclone." + filesystem) is not None and filesystem != "apfs":
                partclone_cmd_list = ["partclone." + filesystem] + Utility.get_partclone_rescue_options(self.is_rescue) + ["--logfile", "/var/log/partclone.log", "--clone",
                                      "--source", partition_key, "--output", "-"]
                filepath = os.path.join(self.dest_dir,
                                        short_device_node + "." + filesystem + "-ptcl-img." + compression_suffix + ".")
                split_cmd_list = ["split", "--suffix-length=2", "--bytes=" + split_size, "-", filepath]
            elif shutil.which("partclone.dd") is not None:
                partclone_cmd_list = ["partclone.dd"]  + Utility.get_partclone_rescue_options(self.is_rescue) + ["--buffer_size=" + partclone_dd_bs, "--logfile",
                                      "/var/log/partclone.log", "--source", partition_key, "--output", "-"]
                filepath = os.path.join(self.dest_dir, short_device_node + ".dd-ptcl-img." + compression_suffix + ".")
                split_cmd_list = ["split", "--suffix-length=2", "--bytes=" + split_size, "-", filepath]
            else:
                failed_message = "Partclone not found."
                GLib.idle_add(self.completed_backup, False, failed_message)
                return False, failed_message

            if self.is_cloning:
                # FIXME: Very ugly design
                # For the cloning case, write a dummy file with the filename that can be scanned by existing Clonezilla
                # image functions
                with open(filepath + "aa", 'wb') as filehandle:
                    # Writes some arbitrary data to temp file so Clonezilla image functions will scan as an
                    # uncompressed image.
                    # FIXME: Very ugly design
                    filehandle.write(b'\x0012345678DEADBEEF')
                continue

            filesystem_backup_message = _("Backup {partition_name} containing filesystem {filesystem} to {destination}").format(partition_name=partition_key, filesystem=filesystem, destination=filepath)
            GLib.idle_add(self.update_main_statusbar, filesystem_backup_message)
            self.logger.write(filesystem_backup_message)

            flat_command_string = Utility.print_cli_friendly("Running ", [partclone_cmd_list, compression_cmd_list, split_cmd_list])
            self.proc['partclone_backup_' + partition_key] = subprocess.Popen(partclone_cmd_list,
                                                                              stdout=subprocess.PIPE,
                                                                              stderr=subprocess.PIPE, env=env,
                                                                              encoding='utf-8')

            self.proc['compression_' + partition_key] = subprocess.Popen(compression_cmd_list,
                                                                  stdin=self.proc[
                                                                      'partclone_backup_' + partition_key].stdout,
                                                                  stdout=subprocess.PIPE, env=env, encoding='utf-8')

            self.proc['split_' + partition_key] = subprocess.Popen(split_cmd_list,
                                                                   stdin=self.proc[
                                                                       'compression_' + partition_key].stdout,
                                                                   stdout=subprocess.PIPE, env=env, encoding='utf-8')

            partclone_stderr = ""
            # Process partclone output. Partclone outputs an update every 3 seconds, so processing the data
            # on the current thread, for simplicity.
            # Poll process.stdout to show stdout live
            while True:
                if self.requested_stop:
                    GLib.idle_add(self.completed_backup, False, _("User requested operation to stop."))
                    return False, _("User requested operation to stop.")

                output = self.proc['partclone_backup_' + partition_key].stderr.readline()
                if self.proc['partclone_backup_' + partition_key].poll() is not None:
                    break
                if output:
                    partclone_stderr += output
                    temp_dict = Partclone.parse_partclone_output(output)
                    if 'completed' in temp_dict.keys():
                        total_progress_float = Utility.calculate_progress_ratio(
                            current_partition_completed_percentage=temp_dict['completed'] / 100.0,
                            current_partition_bytes=self.partitions_to_backup[partition_key]['size'],
                            cumulative_bytes=self.partitions_to_backup[partition_key]['cumulative_bytes'],
                            total_bytes=total_size,
                            image_number=partition_number,
                            num_partitions=len(self.partitions_to_backup))
                        GLib.idle_add(self.update_backup_progress_bar, total_progress_float)
                    if 'remaining' in temp_dict.keys():
                        GLib.idle_add(self.update_backup_progress_status, filesystem_backup_message + "\n\n" + output)
            rc = self.proc['partclone_backup_' + partition_key].poll()

            self.proc['partclone_backup_' + partition_key].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
            self.proc['compression_' + partition_key].stdout.close()  # Allow p2 to receive a SIGPIPE if p3 exits.
            output, err = self.proc['partclone_backup_' + partition_key].communicate()
            self.logger.write("Exit output " + str(output) + "stderr " + str(err))
            if self.proc['partclone_backup_' + partition_key].returncode != 0:
                partition_summary = _("<b>Failed to backup partition</b> {partition_name}").format(partition_name=partition_key) + "\n"
                with self.summary_message_lock:
                    self.summary_message += partition_summary
                self.at_least_one_non_fatal_error = True
                proc_stdout = self.proc['partclone_backup_' + partition_key].stdout
                proc_stderr = self.proc['partclone_backup_' + partition_key].stderr
                extra_info = "\nThe command used internally was:\n\n" + flat_command_string + "\n\n" + "The output of the command was: " + partclone_stderr
                compression_stderr = self.proc['compression_' + partition_key].stderr
                if compression_stderr is not None and compression_stderr != "":
                    extra_info += "\n\n" + str(compression_cmd_list) + " stderr: " + compression_stderr

                # TODO: Try to backup again, but using partclone.dd
                GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                              partition_summary + extra_info)
                # Delete failed partclone files
                failed_partclone_img_path_list = glob.glob(filepath + "*")
                for file_path in failed_partclone_img_path_list:
                    try:
                        os.remove(file_path)
                    except OSError:
                        self.logger.write("Unable to remove: " + file_path)
                        with self.summary_message_lock:
                            self.summary_message += "Unable to remove: " + file_path

            else:
                with self.summary_message_lock:
                    self.summary_message += _("Successful backup of partition {partition_name}").format(partition_name=partition_key) + "\n"

        # GLib.idle_add(self.update_progress_bar, (i + 1) / len(self.restore_mapping_dict.keys()))
        if self.requested_stop:
            GLib.idle_add(self.completed_backup, False, _("User requested operation to stop."))
            return False, _("User requested operation to stop.")

        i += 1
        sleep(1.0)

        """
            partclone_cmd_list = ["partclone", "--logfile", "/tmp/rescuezilla_logfile.txt", "--overwrite", "/dev/"]

              if [ "$fs_p" != "dd" ]; then
    cmd_partclone="partclone.${fs_p} $PARTCLONE_SAVE_OPT -L $partclone_img_info_tmp -c -s $source_dev --output - | $compress_prog_opt"
  else
    # Some parameters for partclone.dd are not required. Here "-c" is not provided by partclone.dd when saving.
    cmd_partclone="partclone.${fs_p} $PARTCLONE_SAVE_OPT --buffer_size ${partclone_dd_bs} -L $partclone_img_info_tmp -s $source_dev --output - | $compress_prog_opt"
  fi
  case "$VOL_LIMIT" in
    [1-9]*)
       # $tgt_dir/${tgt_file}.${fs_pre}-img. is prefix, the last "." is necessary make the output file is like hda1.${fs_pre}-img.aa, hda1.${fs_pre}-img.ab. We do not add -d to make it like hda1.${fs_pre}-img.00, hda1.${fs_pre}-img.01, since it will confuse people that it looks like created by partimage (hda1.${fs_pre}-img.000, hda1.${fs_pre}-img.001)
       cmd_partclone="${cmd_partclone} | split -a $split_suf_len -b ${VOL_LIMIT}MB - $tgt_dir/$(to_filename ${tgt_file}).${fs_pre}-img.${comp_suf}. 2> $split_error"
       ;;
    *)
       cmd_partclone="${cmd_partclone} > $tgt_dir/$(to_filename ${tgt_file}).${fs_pre}-img.${comp_suf} 2> $split_error"
       ;;
  esac
  echo "Run partclone: $cmd_partclone" | tee --append ${OCS_LOGFILE}
  LC_ALL=C eval "(${cmd_partclone} && exit \${PIPESTATUS[0]})"


            cmd_partimage = "partimage $DEFAULT_PARTIMAGE_SAVE_OPT $PARTIMAGE_SAVE_OPT -B gui=no save $source_dev stdout | $compress_prog_opt"
            #case
            #"$VOL_LIMIT" in
            #[1 - 9] *)
            # "$tgt_dir/${tgt_file}." is prefix, the last "." is necessary
            # make the output file is like hda1.aa, hda1.ab.
            # We do not add -d to make it like hda1.00, hda1.01, since it will confuse people that it looks like created by partimage (hda1.000, hda1.001)
            cmd_partimage = "${cmd_partimage} | split -a $split_suf_len -b ${VOL_LIMIT}MB - $tgt_dir/${tgt_file}."
            """

        # Do checksum
        # IMG_ID=$(LC_ALL=C sha512sum $img_dir/clonezilla-img | awk -F" " '{print $1}')" >> $img_dir/Info-img-id.txt

        GLib.idle_add(self.completed_backup, True, "")
        return True, ""

    # Implementation of Clonezilla "check_if_windows_boot_reserve_part" function
    def is_partition_windows_boot_reserved(self, partition_key, mount_point):
        is_windows_reserved = False
        if not os.path.exists(mount_point) and not os.path.isdir(mount_point):
            os.mkdir(mount_point, 0o755)
        process, flat_command_string, failed_message = Utility.run(
            "Mounting NTFS filesystem " + partition_key + " to check whether filesystem is NTFS boot reserved",
            ["mount", "-o", "ro", partition_key, mount_point],
            use_c_locale=True, output_filepath=None,
            logger=self.logger)
        if process.returncode != 0:
            # Not being able to mount the NTFS partition to check if it's NTFS boot reserved is NOT fatal in Clonezilla.
            GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)
            print("Unable to mount NTFS filesystem, assuming *not* Windows boot reserved")
            return is_windows_reserved

        boot_dir_path = os.path.join(mount_point, "Boot")
        bootmgr_path = os.path.join(mount_point, "bootmgr")
        bootsect_bak_path = os.path.join(mount_point, "BOOTSECT.BAK")

        if os.path.isdir(boot_dir_path) and os.path.exists(bootmgr_path) and os.path.exists(bootsect_bak_path):
            is_windows_reserved = True

        is_unmounted, message = Utility.umount_warn_on_busy(partition_key)
        if not is_unmounted:
            # Being unable to unmount the partition that was just mounted is considered fatal.
            self.logger.write(message)
            with self.summary_message_lock:
                self.summary_message += message + "\n"
            GLib.idle_add(self.completed_backup, False, message)
        return is_windows_reserved

    # Intended to be called via event thread
    def update_main_statusbar(self, message):
        context_id = self.main_statusbar.get_context_id("backup")
        self.main_statusbar.pop(context_id)
        self.main_statusbar.push(context_id, message)

    # Intended to be called via event thread
    def update_backup_progress_status(self, message):
        self.backup_progress_status.set_text(message)

    def display_status(self, msg1, msg2):
        GLib.idle_add(self.update_backup_progress_status, msg1 + "\n" + msg2)
        if msg2 != "":
            status_bar_msg = msg1 + ": " + msg2
        else:
            status_bar_msg = msg1
        GLib.idle_add(self.update_main_statusbar, status_bar_msg)

    # Intended to be called via event thread
    def update_backup_progress_bar(self, fraction):
        if self.logger is not None:
            self.logger.write("Updating progress bar to " + str(fraction))
        self.backup_progress.set_fraction(fraction)

    def completed_backup(self, succeeded, message):
        self.update_backup_progress_status("")
        self.main_statusbar.remove_all(self.main_statusbar.get_context_id("backup"))
        if not self.is_cloning:
            backup_timeend = datetime.now()
            duration_minutes = Utility.get_human_readable_minutes_seconds((backup_timeend - self.backup_timestart).total_seconds())
            duration_message = _("Operation took {num_minutes} minutes.").format(num_minutes=duration_minutes)
            self.main_statusbar.remove_all(self.main_statusbar.get_context_id("backup"))

            with self.summary_message_lock:
                if succeeded:
                    if not self.at_least_one_non_fatal_error:
                        self.summary_message = _("Backup saved successfully.") + "\n\n" + self.summary_message + "\n\n" + message + "\n"
                    else:
                        self.summary_message = _("Backup succeeded with some errors:") + "\n\n" + self.summary_message + "\n\n" + message + "\n"
                else:
                    heading = _("Backup operation failed:")
                    self.summary_message = heading + "\n\n" + self.summary_message + "\n\n" + message + "\n"
                    error = ErrorMessageModalPopup(self.builder, self.summary_message, error_heading=heading)

                self.summary_message += duration_message + "\n"
                post_task_action = Utility.get_combobox_key(self.builder.get_object("backup_step8_perform_action_combobox"))
                if post_task_action != "DO_NOTHING":
                    if succeeded:
                        has_scheduled, msg = Utility.schedule_shutdown_reboot(post_task_action)
                        self.summary_message += "\n" + msg
                    else:
                        self.summary_message += "\n" + _("Shutdown/Reboot cancelled due to errors.")

            # TODO: Populate summary page after umounting /mnt/backup (and closing the logger), so than umount errors
            # TODO: are displayed.
            self.populate_summary_page()

            # Clonezilla writes a file named "Info-img-id.txt" which contains a sha512sum of the clonezilla-img log file.
            # "Generate a checksum for identifying the image later. This is based on the file $img_dir/clonezilla-img."
            # It doesn't seem that useful, but because Clonezilla does this, Rescuezilla does this too.
            clonezilla_img_filepath = os.path.join(self.dest_dir, "clonezilla-img")
            info_img_id_filepath = os.path.join(self.dest_dir, "Info-img-id.txt")
            if self.logger is not None:
                self.logger.write("Closing the logfile " + clonezilla_img_filepath + " and generating a tag file for this image: " + info_img_id_filepath)

            if os.path.isfile(clonezilla_img_filepath):
                process, flat_command_string, failed_message = Utility.run("Checksumming clonezilla-img file", ["sha512sum", clonezilla_img_filepath], use_c_locale=True, output_filepath=None, logger=None)
                if process.returncode != 0:
                    GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, failed_message)
                else:
                    sha512sum_output = process.stdout
                    split = sha512sum_output.split("  ")
                    if len(split) == 2:
                        with open(info_img_id_filepath, 'w') as filehandle:
                            filehandle.write("# This checksum is only for identifying the image. Created by the command: sha512sum clonezilla-img\n")
                            filehandle.write('IMG_ID=%s' % split[0])
                            filehandle.flush()
                    else:
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder, "Failed to output checksum file Info-img-id.txt: " + process.stdout + "\n\n" + process.stderr)

        if self.logger:
            self.logger.close()

        if not self.is_cloning:
            is_unmounted, umount_message = Utility.umount_warn_on_busy("/mnt/backup", is_lazy_umount=True)
            if not is_unmounted:
                if self.logger is not None:
                    self.logger.write(umount_message)
                else:
                    print(umount_message)
                with self.summary_message_lock:
                    self.summary_message += umount_message + "\n"
        with self.backup_in_progress_lock:
            self.backup_in_progress = False
        if not self.is_cloning:
            self.completed_backup_callback(succeeded)

    def populate_summary_page(self):
        with self.summary_message_lock:
            if self.logger is not None:
                self.logger.write("Populating summary page with:\n\n" + self.summary_message)
            else:
                print(self.summary_message)
            text_to_display = """<b>{heading}</b>

{message}""".format(heading=_("Backup Summary"), message=GObject.markup_escape_text(self.summary_message))
        self.builder.get_object("backup_step9_summary_program_defined_text").set_markup(text_to_display)

    def print_cli_friendly(self, message, cmd_list_list):
        self.logger.write(message + ". Running: ", end="")
        for cmd_list in cmd_list_list:
            for cmd in cmd_list:
                self.logger.write(cmd + " ", end="")
            self.logger.write(" | ", end="")
