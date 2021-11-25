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
#   MERCHANTABILITY or FITNESS FOR A Ps ARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------
import collections
import os
import subprocess
import threading
import traceback
from datetime import datetime

import gi

from parser.metadata_only_image import MetadataOnlyImage
from parser.sfdisk import Sfdisk

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, GLib

from logger import Logger

from parser.partclone import Partclone
from parser.fsarchiver_image import FsArchiverImage
from utility import ErrorMessageModalPopup, Utility, _


# Signals should automatically propagate to processes called with subprocess.run().

# Rescuezilla's verify logic is loosely based on Clonezilla's "sbin/ocs-chkimg", which simply runs partclone.chkimg
# on Partclone images (after streaming decompression), and also does basic checks on the presence of various partition
# table backups.
#
# TODO: Check veracity of the LVM configuration here (rather than a basic scan during the image scan step),
# TODO: implement ocs-chkimg's basic content of the dd images.
class VerifyManager:
    def __init__(self, builder):
        self.verify_in_progress_lock = threading.Lock()
        self.verify_in_progress = False
        self.builder = builder
        self.verify_progress = self.builder.get_object("verify_progress")
        self.verify_progress_status = self.builder.get_object("verify_progress_status")
        self.main_statusbar = self.builder.get_object("main_statusbar")
        # proc dictionary
        self.proc = collections.OrderedDict()
        self.requested_stop = False

    def is_verify_in_progress(self):
        with self.verify_in_progress_lock:
            return self.verify_in_progress

    def start_verify(self, image_list, completed_callback):
        self.verify_timestart = datetime.now()
        self.image_list = image_list
        self.completed_callback = completed_callback

        with self.verify_in_progress_lock:
            self.verify_in_progress = True
        thread = threading.Thread(target=self.do_verify_wrapper)
        thread.daemon = True
        thread.start()

    # Intended to be called via event thread
    # Sending signals to process objects on its own thread. Relying on Python GIL.
    # TODO: Threading practices here need overhaul. Use threading.Lock() instead of GIL
    def cancel_verify(self):
        # Again, relying on GIL.
        self.requested_stop = True
        if len(self.proc) == 0:
            print("Nothing to cancel")
        else:
            print("Will send cancel signal to " + str(len(self.proc)) + " processes.")
            for key in self.proc.keys():
                process = self.proc[key]
                try:
                    print("Sending SIGTERM to " + str(process))
                    # Send SIGTERM
                    process.terminate()
                except:
                    print("Error killing process. (Maybe already dead?)")
        with self.verify_in_progress_lock:
            self.verify_in_progress = False
        self.completed_verify(False, _("Verify cancelled by user."))

    def do_verify_wrapper(self):
        try:
            self.do_verify()
        except Exception as exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            GLib.idle_add(self.completed_verify, False, _("Error verifying image: ") + tb)
            return

    # TODO: Ideally find ways to consolidate the overlap between this function and aspects of Restore Manager's
    # TODO: do_restore() function
    def do_verify(self):
        self.requested_stop = False

        # Clear proc dictionary
        self.proc.clear()
        self.summary_message_lock = threading.Lock()
        self.summary_message = ""
        env = Utility.get_env_C_locale()

        self.logger = Logger("/tmp/rescuezilla.log." + datetime.now().strftime("%Y%m%dT%H%M%S") + ".txt")
        GLib.idle_add(self.update_progress_bar, 0)

        # Calculate the size across all selected images
        all_images_total_size_estimate = 0
        all_images_num_partitions = 0
        for image in self.image_list:
            if not isinstance(image, FsArchiverImage):
                # Determine the size of all partition across all images. This is used for the weighted progress bar.
                all_images_total_size_estimate += image.size_bytes
                all_images_num_partitions += len(image.image_format_dict_dict.keys())

        cumulative_bytes = 0
        image_number = 0
        total_partition_number = 0
        for image in self.image_list:
            image_number += 1
            image_verify_message = _("Verifying {image_name}").format(image_name=image.absolute_path)
            self.logger.write(image_verify_message)
            GLib.idle_add(self.display_status, image_verify_message, image_verify_message)

            if self.requested_stop:
                GLib.idle_add(self.completed_verify, False, _("User requested operation to stop."))
                return

            with self.summary_message_lock:
                self.summary_message += image.absolute_path + "\n"

            if isinstance(image, FsArchiverImage):
                with self.summary_message_lock:
                    self.summary_message += _("⚠") + " " + "Verifying FsArchiver images not yet supported\n"
                continue
            if isinstance(image, MetadataOnlyImage):
                with self.summary_message_lock:
                    self.summary_message += _("⚠") + " " + "Verifying VM images not yet supported\n"
                continue

            if image.is_needs_decryption:
                with self.summary_message_lock:
                    self.summary_message += _("⚠") + " " + "Verifying encrypted images not supported. Carefully decrypting on the command-line may be a temporary workaround.\n"
                continue

            if image.has_partition_table():
                mbr_path = image.get_absolute_mbr_path()
                mbr_size = int(os.stat(mbr_path).st_size)

                # Some image formats (like Clonezilla) have post MBR gap separate from the actual MBR
                post_mbr_size = 0
                if 'absolute_path' in image.post_mbr_gap_dict.keys():
                    post_mbr_size += int(os.stat(image.post_mbr_gap_dict['absolute_path']).st_size)

                if (mbr_size + post_mbr_size) <= 512:
                    if Sfdisk.has_dos_partition_table(image.normalized_sfdisk_dict):
                        self.summary_message += _("❌") + " " + _("The backup's bootloader data is shorter than expected. If the backup contained certain bootloaders like GRUB, during a restore operation Rescuezilla will try and re-install the bootloader.") + "\n"
                else:
                    self.summary_message += _("✔") + " " + _("MBR backup appears correct.") + "\n"
            else:
                self.summary_message += _("No partition table found.") + "\n"

            if image.normalized_sfdisk_dict['file_length'] == 0:
                self.summary_message += _("❌") + " " + _("Sfdisk partition table file is empty or missing.") + "\n"
            else:
                self.summary_message += _("✔") + " " + _("Sfdisk partition table file is present.") + "\n"

            for partition_key in image.image_format_dict_dict.keys():
                total_partition_number += 1
                if self.requested_stop:
                    GLib.idle_add(self.completed_verify, False, _("User requested operation to stop."))
                    return

                if 'estimated_size_bytes' in image.image_format_dict_dict[partition_key].keys():
                    partition_estimated_size_bytes = image.image_format_dict_dict[partition_key]['estimated_size_bytes']
                elif 'absolute_filename_glob_list' in image.image_format_dict_dict[partition_key].keys():
                    # TODO: Move this to the image scanning step.
                    print("Calculating estimated size from file size")
                    partition_estimated_size_bytes = Utility.count_total_size_of_files_on_disk(image.image_format_dict_dict[partition_key]['absolute_filename_glob_list'], "uncompressed")
                else:
                    partition_estimated_size_bytes = 0

                filesystem_verify_message = _("Partition {partition}").format(partition=partition_key)
                self.logger.write(image_verify_message)
                GLib.idle_add(self.display_status, image_verify_message + " " + filesystem_verify_message,
                              filesystem_verify_message)

                total_progress_float = Utility.calculate_progress_ratio(current_partition_completed_percentage=0,
                                                                        current_partition_bytes=partition_estimated_size_bytes,
                                                                        cumulative_bytes=cumulative_bytes,
                                                                        total_bytes=all_images_total_size_estimate,
                                                                        image_number=total_partition_number,
                                                                        num_partitions=all_images_num_partitions)
                GLib.idle_add(self.update_progress_bar, total_progress_float)

                if 'type' in image.image_format_dict_dict[partition_key].keys():
                    image_type = image.image_format_dict_dict[partition_key]['type']
                    if image_type == 'swap':
                        self.summary_message += _("⚠") + " " + partition_key + ": verifying swap partition images not yet supported.\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue
                    if image_type == 'missing':
                        self.summary_message += _("❌") + " " + partition_key + ": partition is missing.\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue
                    if 'dd' == image_type or image.image_format_dict_dict[partition_key]['binary'] == "partclone.dd":
                        self.summary_message += _("⚠") + " " + partition_key + ": verifying raw dd images not yet supported.\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue
                    elif 'partclone' == image_type:
                        cat_cmd_list = ["cat"] + image.image_format_dict_dict[partition_key][
                            'absolute_filename_glob_list']
                        decompression_cmd_list = Utility.get_decompression_command_list(
                            image.image_format_dict_dict[partition_key]['compression'])
                        verify_command_list = ["partclone.chkimg", "--source", "-"]
                    elif 'partimage' == image_type:
                        self.summary_message += _("⚠") + " " + partition_key + ": verifying PartImage images not yet supported.\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue
                    elif 'ntfsclone' == image_type:
                        self.summary_message += _("⚠") + " " + partition_key + ": Verifying NTFSclone images not yet supported.\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue
                    elif "unknown" != image_type:
                        self.summary_message += _("❌") + " " + partition_key + ": unknown image type.\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue
                    else:
                        message = "Unhandled type" + image_type + " from " + partition_key
                        self.logger.write(message)
                        with self.summary_message_lock:
                            self.summary_message += message + "\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue

                    flat_command_string = Utility.print_cli_friendly(image_type + " command ",
                                                                     [cat_cmd_list, decompression_cmd_list,
                                                                      verify_command_list])
                    verify_cat_proc_key = 'cat_' + partition_key
                    self.proc[verify_cat_proc_key] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE,
                                                                      env=env, encoding='utf-8')
                    verify_decompression_proc_key = 'decompression_' + image.absolute_path + "_" + partition_key
                    self.proc[verify_decompression_proc_key] = subprocess.Popen(decompression_cmd_list,
                                                                                stdin=self.proc[
                                                                                    verify_cat_proc_key].stdout,
                                                                                stdout=subprocess.PIPE, env=env,
                                                                                encoding='utf-8')

                    verify_chkimg_proc_key = image_type + '_verify_' + image.absolute_path + "_" + partition_key
                    self.proc[verify_chkimg_proc_key] = subprocess.Popen(verify_command_list,
                                                                         stdin=self.proc[
                                                                             verify_decompression_proc_key].stdout,
                                                                         stdout=subprocess.PIPE,
                                                                         stderr=subprocess.PIPE, env=env,
                                                                         encoding='utf-8')

                    # Process partclone output. Partclone outputs an update every 3 seconds, so processing the data
                    # on the current thread, for simplicity.
                    # Poll process.stdout to show stdout live
                    proc_stdout = ""
                    proc_stderr = ""
                    while True:
                        if self.requested_stop:
                            GLib.idle_add(self.completed_verify, False, _("User requested operation to stop."))
                            return False, _("User requested operation to stop.")

                        output = self.proc[verify_chkimg_proc_key].stderr.readline()
                        proc_stderr += output
                        if self.proc[verify_chkimg_proc_key].poll() is not None:
                            break
                        if output and ("partclone" == image_type or "dd" == image_type):
                            temp_dict = Partclone.parse_partclone_output(output)
                            if 'completed' in temp_dict.keys():
                                total_progress_float = Utility.calculate_progress_ratio(
                                    current_partition_completed_percentage=temp_dict['completed'] / 100.0,
                                    current_partition_bytes=partition_estimated_size_bytes,
                                    cumulative_bytes=cumulative_bytes,
                                    total_bytes=all_images_total_size_estimate,
                                    image_number=total_partition_number,
                                    num_partitions=len(image.image_format_dict_dict[partition_key].keys()))
                                GLib.idle_add(self.update_progress_bar, total_progress_float)
                            if 'remaining' in temp_dict.keys():
                                GLib.idle_add(self.update_verify_progress_status,
                                              filesystem_verify_message + "\n\n" + output)
                        elif "partimage" == image_type:
                            self.display_status("partimage: " + filesystem_verify_message, "")
                        elif "ntfsclone" == image_type:
                            self.display_status("ntfsclone: " + filesystem_verify_message, "")

                        rc = self.proc[verify_chkimg_proc_key].poll()

                    self.proc[verify_cat_proc_key].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
                    if "unknown" != image_type:
                        self.proc[
                            verify_decompression_proc_key].stdout.close()  # Allow p2 to receive a SIGPIPE if p3 exits.
                    stdout, stderr = self.proc[verify_chkimg_proc_key].communicate()
                    rc = self.proc[verify_chkimg_proc_key].returncode
                    proc_stdout += stdout
                    proc_stderr += stderr
                    self.logger.write("Exit output " + str(rc) + ": " + str(proc_stdout) + "stderr " + str(proc_stderr))
                    if self.proc[verify_chkimg_proc_key].returncode != 0:
                        partition_summary = _("❌") + " " + _("Unable to verify.") + _("Partition {partition_number}").format(partition_number=partition_key) + "\n"
                        extra_info = "\nThe command used internally was:\n\n" + flat_command_string + "\n\n" + "The output of the command was: " + str(
                            proc_stdout) + "\n\n" + str(proc_stderr)
                        decompression_stderr = self.proc[verify_decompression_proc_key].stderr
                        if decompression_stderr is not None and decompression_stderr != "":
                            extra_info += "\n\n" + decompression_cmd_list[0] + " stderr: " + decompression_stderr
                        GLib.idle_add(ErrorMessageModalPopup.display_nonfatal_warning_message, self.builder,
                                      partition_summary + extra_info)
                        with self.summary_message_lock:
                            self.summary_message += partition_summary
                        cumulative_bytes += partition_estimated_size_bytes
                        continue
                    else:
                        self.summary_message += _("✔") + _("{partition}: filesystem image successfully verified.").format(partition=partition_key) + "\n"
                        cumulative_bytes += partition_estimated_size_bytes
                        continue

                cumulative_bytes += partition_estimated_size_bytes

            with self.summary_message_lock:
                self.summary_message += "\n\n"

        GLib.idle_add(self.completed_verify, True, "")
        return

    def display_status(self, msg1, msg2):
        GLib.idle_add(self.update_verify_progress_status, msg1 + "\n" + msg2)
        if msg2 != "":
            status_bar_msg = msg1 + ": " + msg2
        else:
            status_bar_msg = msg1
        GLib.idle_add(self.update_main_statusbar, status_bar_msg)

    # Intended to be called via event thread
    def update_main_statusbar(self, message):
        context_id = self.main_statusbar.get_context_id("verify")
        self.main_statusbar.push(context_id, message)

    # Intended to be called via event thread
    def update_verify_progress_status(self, message):
        self.verify_progress_status.set_text(message)

    # Intended to be called via event thread
    def update_progress_bar(self, fraction):
        self.logger.write("Updating progress bar to " + str(fraction) + "\n")
        self.verify_progress.set_fraction(fraction)

    # Expected to run on GTK event thread
    def completed_verify(self, succeeded, message):
        verify_timeend = datetime.now()
        duration_minutes = Utility.get_human_readable_minutes_seconds((verify_timeend - self.verify_timestart).total_seconds())

        self.main_statusbar.remove_all(self.main_statusbar.get_context_id("verify"))
        with self.verify_in_progress_lock:
            self.verify_in_progress = False
        if succeeded:
            print("Success")
        else:
            with self.summary_message_lock:
                self.summary_message += message + "\n"
            error = ErrorMessageModalPopup(self.builder, message)
            print("Failure")
        with self.summary_message_lock:
            self.summary_message += "\n" + _("Operation took {num_minutes} minutes.").format(
                num_minutes=duration_minutes) + "\n"
        self.populate_summary_page()
        self.logger.close()
        self.completed_callback(succeeded)

    def populate_summary_page(self):
        with self.summary_message_lock:
            self.logger.write("Populating summary page with:\n\n" + self.summary_message)
            text_to_display = _("""<b>{heading}</b>

{message}""").format(heading=_("Verification Summary"), message=GObject.markup_escape_text(self.summary_message))
        self.builder.get_object("verify_step4_summary_program_defined_text").set_markup(text_to_display)
