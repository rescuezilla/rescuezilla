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
import gettext
import locale
import math
import os
import pwd
import re
import shutil
import subprocess
import threading
import time
from contextlib import contextmanager
from queue import Queue
from threading import Thread
from time import sleep

import gi

from wizard_state import RESCUEZILLA_MOUNT_TMP_DIR

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

"""Utility functions to eg, display busy dialog boxes or error messages
"""


def _(string):
    return gettext.gettext(string)


class PleaseWaitModalPopup:
    def __init__(self, builder, title, message, on_close_callback=None):
        self._main_window = builder.get_object("main_window")
        self._dialog = Gtk.Dialog(title, self._main_window, Gtk.DialogFlags.MODAL)
        self._dialog.vbox.set_halign(Gtk.Align.CENTER)
        self._dialog.vbox.set_valign(Gtk.Align.CENTER)
        self._dialog.vbox.set_margin_left(30)
        self._dialog.vbox.set_margin_right(30)
        self._dialog.vbox.set_margin_top(0)
        self._dialog.vbox.set_margin_bottom(15)

        self._dialog.connect("response", self._response)
        label = Gtk.Label(label=message, xalign=0)
        label.set_halign(Gtk.Align.CENTER)
        label.set_padding(xpad=0, ypad=10)
        label.show()
        self._dialog.vbox.pack_start(label, expand=True, fill=True, padding=0)

        self.secondary_label = Gtk.Label("", xalign=0)
        self.secondary_label.set_halign(Gtk.Align.CENTER)
        self.secondary_label.set_padding(xpad=0, ypad=10)
        self.secondary_label.show()
        self.secondary_label.set_visible(False)
        self._dialog.vbox.pack_start(self.secondary_label, expand=True, fill=True, padding=0)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.show()
        self._dialog.vbox.pack_start(self._progress_bar, expand=True, fill=True, padding=0)

        self.timeout_tag = GLib.timeout_add(50, self.pulse)

        self._on_close_callback = on_close_callback

    def show(self):
        self._main_window.set_sensitive(False)
        self._dialog.set_keep_above(True)
        self._dialog.show()

    def _response(self, response_id, user_param1):
        print("User has closed the please wait popup.")
        if self._on_close_callback is not None:
            GLib.idle_add(self._on_close_callback)

    def destroy(self):
        self._main_window.set_sensitive(True)
        GLib.source_remove(self.timeout_tag)
        self._dialog.destroy()

    def set_secondary_label_text(self, message):
        self.secondary_label.set_visible(True)
        self.secondary_label.set_text(message)

    """ Pulse progress progress bar """

    def pulse(self):
        self._progress_bar.pulse()
        return True


class ErrorMessageModalPopup(Gtk.MessageDialog):
    def __init__(self, builder, error_content, error_heading=""):
        Gtk.MessageDialog.__init__(self, type=Gtk.MessageType.ERROR,
                                         buttons=Gtk.ButtonsType.OK,
                                         message_format=error_heading)
        print("Displaying error box: " + error_heading + "\n\n" + error_content)
        self.set_resizable(True)
        self.set_default_size(width=650, height=400)
        label = Gtk.Label(error_content)
        scrolled_window = Gtk.ScrolledWindow()
        # Error messages should be able to be copy-and-pasted
        label.set_selectable(True)
        label.set_line_wrap(True)
        scrolled_window.add_with_viewport(label)
        scrolled_window.set_visible(True)
        box = self.get_content_area()
        box.pack_end(scrolled_window, expand=True, fill=True, padding=0)
        self.show_all()

        self._main_window = builder.get_object("main_window")

        self.vbox.set_margin_left(30)
        self.vbox.set_margin_right(30)
        self.vbox.set_margin_bottom(15)

        self.connect("response", self._response)
        self._main_window.set_sensitive(False)
        self.set_keep_above(True)
        self.show()

    """ Close the window on clicking the 'OK' button """

    def _response(self, response_id, user_param1):
        self._main_window.set_sensitive(True)
        self.destroy()

    @staticmethod
    def display_nonfatal_warning_message(builder, message):
        print(message)
        ErrorMessageModalPopup(builder, message)


class AreYouSureModalPopup:
    def __init__(self, builder, message, callback):
        self._main_window = builder.get_object("main_window")
        self._dialog = Gtk.MessageDialog(parent=self._main_window, type=Gtk.MessageType.ERROR,
                                         buttons=Gtk.ButtonsType.YES_NO, message_format=message)
        self._callback = callback
        self._dialog.connect("response", self._response)
        self._main_window.set_sensitive(False)
        self._dialog.set_keep_above(True)
        self._dialog.show()

    """ Selecting a folder """

    def _response(self, dialog, response_id):
        print("Received response " + str(response_id))
        if response_id == Gtk.ResponseType.YES:
            GLib.idle_add(self._callback, True)
        elif response_id == Gtk.ResponseType.NO:
            GLib.idle_add(self._callback, False)
        self._main_window.set_sensitive(True)
        self._dialog.destroy()


class BrowseSelectionPopup:
    def __init__(self, builder, callback, default_directory, is_allow_selecting_folder_outside_mount,
                 select_file=False):
        if select_file:
            action = Gtk.FileChooserAction.OPEN
        else:
            action = Gtk.FileChooserAction.SELECT_FOLDER
        self._main_window = builder.get_object("main_window")
        #FIXME: Make this a validator
        self.is_allow_selecting_folder_outside_mount = is_allow_selecting_folder_outside_mount
        # Label to update with the selected folder
        self._dialog = Gtk.FileChooserDialog(parent=self._main_window, action=action,
                                             buttons=(Gtk.STOCK_OK, Gtk.ResponseType.OK))
        if self._dialog.set_current_folder(default_directory):
            print("Changed folder selection popup directory to " + default_directory)
        else:
            print("Failed to change folder selection popup directory to " + default_directory)

        self.callback = callback
        self._dialog.connect("response", self._response)
        self._main_window.set_sensitive(False)
        self._dialog.set_keep_above(True)
        self._dialog.show()

    """ Selecting a folder """

    def _response(self, dialog, response_id):
        print("Received response " + str(response_id) + " and file activated callback with folder " + str(
            self._dialog.get_filename()))
        if response_id == Gtk.ResponseType.OK:
            self.callback(self._dialog.get_filename(), self.is_allow_selecting_folder_outside_mount)
        self._main_window.set_sensitive(True)
        self._dialog.destroy()


# From https://stackoverflow.com/questions/2554185/match-groups-in-python/2555047#2555047
# Won't be required for Python >3.8
class REMatcher(object):
    def __init__(self, matchstring):
        self.matchstring = matchstring

    def match(self, regexp):
        self.rematch = re.match(regexp, self.matchstring)
        return bool(self.rematch)

    def group(self, i):
        return self.rematch.group(i)


class Utility:
    # Helper function copied from [1] that allows for running strptime() against a custom locale (usually, 'C')
    # [1] https://stackoverflow.com/a/24070673/4745097
    LOCALE_LOCK = threading.Lock()
    @contextmanager
    def setlocale(name):
        with Utility.LOCALE_LOCK:
            saved = locale.setlocale(locale.LC_ALL)
            try:
                yield locale.setlocale(locale.LC_ALL, name)
            finally:
                locale.setlocale(locale.LC_ALL, saved)

    @staticmethod
    def is_user_valid(target_user):
        try:
            pwd.getpwnam(target_user)
            return True
        except KeyError:
            return False

    # Background: The Rescuezilla frontend uses PolKit to elevate from the standard user to root user, as is required to
    # access harddrive block devices. To open graphical tools from an application running as root as a non-privileged
    # user requires this wrapper.
    @staticmethod
    def open_app_as_target_user(target_user, process_list):
        current_user = pwd.getpwuid(os.getuid()).pw_name
        print("Current user is '" + current_user + "'. As user '" + target_user + "' launching: " + str(process_list))
        # Launch detached subprocess as target user
        sudo_process_list = ["sudo", "-u", target_user] + process_list
        if Utility.is_user_valid(target_user):
            print("Running " + str(process_list))
            subprocess.Popen(sudo_process_list, start_new_session=True)
            # TODO: Check return code of otherwise forking process
            return True, ""
        else:
            # TODO: Find a way to arbitrarily launch graphical applications as the local non-root user from Rescuezilla's root process.
            error_message = "Cannot run: " + str(sudo_process_list)
            error_message += "\n\nThe user named \"" + target_user + "\" does not exist. Are you using Rescuezilla outside the official live environment?"
            error_message += "\n\nPlease navigate to the specified location manually."
            return False, error_message

    # Opens URL in web browser using non-root user, for users that need to click on a link within the Rescuezilla
    # frontend (eg, to access the Rescuezilla forum to receive support).
    # Clicking on a URL within Rescuezilla using a GTK LinkButton attempts to open a web
    # browser as root user (which modern web browsers do not allow). Fortunately most end-users will be running the X
    # Windowing System session as a non-root user,
    @staticmethod
    def open_url_as_user(target_user, url):
        # Default web browser symlink as configured by X Desktop Group's standard command (rather than Debian
        # Alternatives System configured web browser).
        return Utility.open_app_as_target_user(target_user, ["xdg-open", url])

    @staticmethod
    def read_file_into_string(file_path):
        with open(file_path, 'r') as file:
            data = file.read()
        return data

    @staticmethod
    def read_linebreak_delimited_file_into_list(file_path):
        with open(file_path) as f:
            lines = f.read().splitlines()
        return lines

    @staticmethod
    def read_space_delimited_file_into_list(file_path):
        with open(file_path) as f:
            lines = f.read().strip().split(" ")
            map(str.strip, lines)
            # Consider file containing just a newline as empty list.
            if len(lines) == 1 and lines[0] == "":
                lines = []
        return lines

    @staticmethod
    def _split_short_device_on_p(base_device_node):
        part_split = re.split("p", base_device_node)
        if len(part_split) == 1:
            base_device_node = part_split[0]
            partition_number = 0
            return base_device_node, partition_number
        elif len(part_split) == 2:
            base_device_node = part_split[0]
            partition_number = int(part_split[1])
            return base_device_node, partition_number
        else:
            raise ValueError("Unable to split: " + base_device_node)

    # For a given partition, use regular expressions to return the UNIX base device node string,
    # and the partition number.
    #
    # Input arguments:
    #   input_partition: A partition device string. Eg, '/dev/sda5', 'nvme0n1p3', 'sda'
    #
    # Returns:
    #   List in the form (sda, 5) or (nvme0n1, 3), (sda, 0), which contains:
    #     * The base device node
    #     * Partition number (eg. 5 from "sda5" or 3 from "nvme0n1p3" or 0 from 'sda')
    #
    # The unit test provides clear examples.
    @staticmethod
    def split_device_string(device_node):
        short_device_node = re.sub('/dev/', '', device_node)
        # Following comment copied from Clonezilla "is_partition" function:
        # SD card: /dev/mmcblk0p1, /dev/mmcblk0p2, /dev/mmcblk0p3...
        # NBD device: /dev/nbd0p1, /dev/nbd0p2...
        # NVME device: /dev/nvme0n1p1, /dev/nvme0n1p2, /dev/nvme1n1p1, /dev/nvme1n1p2
        # FakeRAID: with nodmraid boot parameter, /dev/md126p1, /dev/md126p2...
        if short_device_node.startswith("nvme") \
                or short_device_node.startswith("mmcblk") \
                or short_device_node.startswith("md") \
                or short_device_node.startswith("nbd"):
            return Utility._split_short_device_on_p(short_device_node)
        # Following comment copied from Clonezilla "is_partition" function:
        # Loop device: /dev/loop0, /dev/loop0p1, /dev/loop0p2
        elif short_device_node.startswith("loop"):
            # The string 'loop' contains a 'p' character, so temporarily remove it before splitting.
            short_device_node = re.sub('loop', '', short_device_node)
            base, partition_number = Utility._split_short_device_on_p(short_device_node)
            base = "loop" + base
            return base, partition_number
        elif short_device_node.startswith("sr"):
            # CD/DVD drives: /dev/sr0, /dev/sr1
            # Such drives tend to have ISO9660 filesystems directly on disks and not support standard partition tables.
            m = REMatcher(short_device_node)
            if m.match(r"(sr[0-9]*)"):
                base_device_node = m.group(1)
                partition_number = 0
                return base_device_node, partition_number
            else:
                raise ValueError("Unable to split:" + device_node)
        else:
            m = REMatcher(short_device_node)
            # Following comment block copied from Clonezilla "is_partition" function:
            # IDE and SCSI disk partition: /dev/hda1, /dev/hdb1, /dev/sda1, /dev/sdb1...
            # KVM virtual disk partition: /dev/vda1, /dev/vdb1...
            # Xen virtual disk partition: /dev/xvda1, /dev/xvdb1, /dev/xdvc1...
            if m.match(r"(hd[a-zA-Z]+|sd[a-zA-Z]+|vd[a-zA-Z]+|xvd[a-zA-Z]+)([0-9]*)"):
                base_device_node = m.group(1)
                # Handle eg, "/dev/sda4" case
                partition_string = m.group(2)
                if partition_string != "":
                    partition_number = int(partition_string)
                else:
                    # Handle eg, "/dev/sda" case
                    partition_number = 0
                return base_device_node, partition_number
            elif "/" in short_device_node:
                # Detected multipath device node, or LVM logical volume.
                #
                # Following comment copied from Clonezilla "is_partition" function:
                #     CCISS RAID disk partition: /dev/cciss/c0d0p1, /dev/cciss/c0d1p1...
                #     Mylex ExtremeRAID-2000 SCSI RAID controller: /dev/rd/c0d0p1, /dev/rd/c0d1p1...
                #     Compaq Smart Array controller: /dev/ida/c0d0p1, /dev/ida/c0d1p2...
                #     and
                #     Just in case. User might use /dev/cciss/c0d0 to get the part number.
                #     Here we will continue only if $dev_ is a partition
                #     Otherwise
                #     echo cciss/c0d0 | sed -r -e 's/^.*[0-9]{1,}(p[0-9]{1,})$/\1/g'
                #     will get "cciss/c0d0". However, it should be "".
                #     It's easier we use: sed -r -e 's|cciss/c[0-9]+d[0-9]+||g' for cciss/c0d0p3 cases
                #
                # However, `man cciss` suggests that "obsolete driver was removed from the kernel in version 4.14, as it
                # is superseded by the hpsa(4) driver in newer kernels". Indeed, `man hpsa` suggests "Logical drives are
                # accessed via the SCSI disk driver (sd(4)), tape drives via the SCSI tape driver (st(4)), and the RAID
                # controller via the SCSI generic driver (sg(4)), with device nodes named /dev/sd*, /dev/st*, and
                # /dev/sg*, respectively."
                #
                # TODO: Evaluate https://www.kernel.org/doc/html/latest/admin-guide/devices.html and improve upon
                # TODO: handling device nodes in that may occur in modern Linux kernels.
                #
                # For now, replace forward slash with dash as that's how Clonezilla LVM
                # /dev/volumegroup/logicalvolume paths get converted to volumegroup-logicalvolume.
                short_device_node = re.sub('/', '-', short_device_node)
            else:
                raise ValueError("Unable to split:" + device_node)

    # Given a UNIX base device node string, and an end-user friendly partition number returns a combined string that
    # handles a number of different device naming styles.
    #
    # Input arguments:
    #   base_device_node         : Eg, 'sdf', 'sda', 'nvme4n3' or 'nvme0n1'.
    #   partition_number         : Eg, '5', '0', '0' or '3'
    #
    # Returns:
    #     * combined string      : Eg, 'sdf5', 'sda', 'nvme4n3' or 'nvme0n1p3' (notice the 'p' for the NVMe drive)
    @staticmethod
    def join_device_string(base_device_node, partition_number):
        # Undo the Clonezilla multipath device node / LVM flattening.
        # TODO: Evaluate whether this is acceptable for all Clonezilla input images: are there device nodes or LVM paths
        # TODO: which contain dashes that shouldn't be substituted?
        short_base_device_node = re.sub('/dev/', '', base_device_node)
        base_device_node = re.sub('-', '/', base_device_node)
        if short_base_device_node.startswith("nvme") \
                or short_base_device_node.startswith("mmcblk") \
                or short_base_device_node.startswith("md") \
                or short_base_device_node.startswith("nbd") \
                or short_base_device_node.startswith("loop"):
            if partition_number != 0:
                joined = base_device_node + "p" + str(partition_number)
            else:
                joined = base_device_node
        else:
            if partition_number != 0:
                joined = base_device_node + str(partition_number)
            else:
                joined = base_device_node
        return joined

    @staticmethod
    def is_base_device_node(device_node):
        try:
            base_device_node, partition_number = Utility.split_device_string(device_node)
        except Exception:
            print("Could not split " + device_node)
            return False

        if partition_number == 0:
            return True
        else:
            return False

    # FIXME: Make better
    @staticmethod
    def get_env_C_locale():
        # Copy locale (containing PATH etc), and update the locale
        env = os.environ.copy()
        env['locale'] = "C"
        env['LANG'] = "C"
        return env

    # Get the memory bus width (that is, 32 or 64 bit computing). End-users are expected to read the term "64bit",
    # but cannot be expected to read the intimidating term Linux distribution arch 'i386'/'amd64' (which is also
    # misleading as Debian/Ubuntu's i386 version is actually i686). Nor do users need to read the "machine hardware
    # name" 'i686'/'x86_64' (from `arch` or `uname -m`).
    @staticmethod
    def get_memory_bus_width():
        process, flat_cmd_string, failed_message = Utility.run("Get memory bus width", ["getconf", "LONG_BIT"], use_c_locale=True)
        if process.returncode == 0:
            memory_bus_width = process.stdout.strip() + "bit"
            return memory_bus_width
        else:
            raise Exception(failed_message)

    @staticmethod
    def get_cli_friendly(cmd_list_list):
        flat_command_string = ""
        i = 0
        for cmd_list in cmd_list_list:
            for cmd in cmd_list:
                flat_command_string += cmd + " "
            i += 1
            if i < len(cmd_list_list):
                flat_command_string += "| "
        return flat_command_string


    @staticmethod
    def print_cli_friendly(message, cmd_list_list):
        print(message + ". Running: ", end="")
        flat_command_string = Utility.get_cli_friendly(cmd_list_list)
        # Print newline to flush the buffer
        print(flat_command_string)
        return flat_command_string

    @staticmethod
    def get_human_readable_minutes_seconds(seconds):
        duration_minutes, duration_seconds = divmod(seconds, 60)
        frac, whole = math.modf(duration_minutes / 60)
        # 1 decimal place (55.3 minutes)
        return "{:.1f}".format(duration_minutes + frac)

    @staticmethod
    def run(short_description, cmd_list, use_c_locale, output_filepath=None, logger=None):
        if use_c_locale:
            env = Utility.get_env_C_locale()
        else:
            env = os.environ.copy()
        flat_command_string = Utility.print_cli_friendly(short_description, [cmd_list])
        process = subprocess.run(cmd_list, encoding='utf-8', capture_output=True, env=env)
        logging_output = short_description + ": " + flat_command_string + " returned " + str(process.returncode) + ": " + process.stdout + " " + process.stderr + "\n"
        if logger is None:
            print(logging_output)
        else:
            logger.write(logging_output)

        if output_filepath is not None:
            with open(output_filepath, 'a+') as filehandle:
                # TODO confirm encoding
                filehandle.write('%s' % process.stdout)
                filehandle.flush()

        fail_description = _("Failed to run command: ") + flat_command_string + "\n\n" + process.stdout + "\n" + process.stderr + "\n\n"
        return process, flat_command_string, fail_description

    # Similar to run above, but checks whether the is_shutdown() function has triggered.
    # TODO: Combine this function with the above -- see [1] for a discussion.
    # [1] https://eli.thegreenplace.net/2017/interacting-with-a-long-running-child-process-in-python/
    @staticmethod
    def interruptable_run(short_description, cmd_list, use_c_locale, is_shutdown_fn):
        if use_c_locale:
            env = Utility.get_env_C_locale()
        else:
            env = os.environ.copy()
        flat_command_string = Utility.print_cli_friendly(short_description, [cmd_list])
        process = subprocess.Popen(cmd_list, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   env=env)
        while True:
            # This loop only ends if the Popen process has completed.
            if process.poll() is not None:
                break
            if is_shutdown_fn():
                process.terminate()
                sleep(1)
                process.kill()
                continue
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                # timeout expired
                continue

        # This communicate should return immediately. Not stderr_data is None because of the redirection above.
        stdout_data, stderr_data = process.communicate()
        logging_output = short_description + ": " + flat_command_string + " returned " + str(
            process.returncode) + ": " + stdout_data + "\n"
        print(logging_output)

        fail_description = _("Failed to run command: ") + flat_command_string + "\n\n" + stdout_data + "\n\n"
        return process, flat_command_string, fail_description

    # Certain NBD commands appear to be unreliable. Due to NBD is handled in the kernel, apparently.
    @staticmethod
    def retry_run(short_description, cmd_list, expected_error_msg, retry_interval_seconds, timeout_seconds, is_shutdown_fn=None):
        if is_shutdown_fn is None:
            # If no is shutdown function specified, make a function that simply always return False
            is_shutdown_fn = lambda : False

        num_tries = 0
        max_tries = timeout_seconds / retry_interval_seconds
        while num_tries < max_tries:
            num_tries += 1
            process, flat_command_string, fail_description = Utility.interruptable_run(short_description, cmd_list, use_c_locale=True, is_shutdown_fn=is_shutdown_fn)
            if process.returncode != 0:
                if expected_error_msg in fail_description:
                    time.sleep(retry_interval_seconds)
                else:
                    # If the error message was unexpected, return immediately
                    return False, fail_description
            else:
                return True, process.stdout
        return False, "Rescuezilla retry timeout exceeded"

    @staticmethod
    def umount_warn_on_busy(mount_point, is_lazy_umount=False):
        if is_lazy_umount:
            umount_cmd = ['umount', "--lazy", mount_point]
        else:
            umount_cmd = ['umount', mount_point]
        umount_process, flat_command_string, umount_failed_message = Utility.run("umount", umount_cmd, use_c_locale=False)
        # Cannot rely on umount return code, as it returns an error if there's nothing mounted and it's not possible
        # to distinguish the situation.
        findmnt_process, flat_command_string, failed_message = Utility.run("findmnt",
                                                           ["findmnt", "--raw", "--noheadings", "--output", "SOURCE",
                                                            mount_point], use_c_locale=False)
        if findmnt_process.stdout != "" or findmnt_process.stderr != "":
            return False, umount_failed_message
        else:
            return True, ""

    # Calculate total percentage progress ratio. Ideally use the number of bytes in each partition, but
    # use the number of partitions if this information is not available.
    @staticmethod
    def calculate_progress_ratio(current_partition_completed_percentage,
                                 current_partition_bytes,
                                 cumulative_bytes,
                                 total_bytes,
                                 image_number,
                                 num_partitions):
        if total_bytes != 0:
            return (current_partition_bytes * current_partition_completed_percentage + cumulative_bytes) / total_bytes
        else:
            # Fallback to counting partitions if total bytes happen to be zero.
            return current_partition_completed_percentage / num_partitions + (image_number - 1) / num_partitions

    # Useful for non-blocking IO (see below)
    @staticmethod
    def enqueue_stream(stream, queue):
        for line in iter(stream.readline, b''):
            queue.put(line)
        stream.close()

    # Adapted from: https://stackoverflow.com/a/4896288/4745097
    @staticmethod
    def nonblocking_subprocess_pipe_queue(process):
        queue = Queue()
        t = Thread(target=Utility.enqueue_stream, args=(process.stdout, queue))
        t.daemon = True  # thread dies with the program
        t.start()
        t2 = Thread(target=Utility.enqueue_stream, args=(process.stderr, queue))
        t2.daemon = True  # thread dies with the program
        t2.start()
        return queue

    # Many image formats use "partclone.dd" to create raw sector-by-sector images. These images are often compressed,
    # typically with gzip. Unfortunately, partclone.info can't read dd images, and gzip compression doesn't provide
    # an accurate file size without decompression the entire archive (see `man gunzip` for documentation on the
    # limitations of its --list parameter).
    #
    # A reasonably accurate estimate is important to eg, ensure that during restore operation the progress bar
    # represents the amount of data that has actually been restored.
    #
    # Instead, simply counting the compressed file size provides a rough estimate. And for other compression formats
    # this function may be expanded to extract more accurate numbers.
    @staticmethod
    def count_total_size_of_files_on_disk(split_file_array, compression):
        # For gzip compression, could apply a reasonable eg, 40% compression ratio on to get a more accurate
        # uncompressed estimate, but this seems bit unnecessary.
        total_bytes = 0
        for file_path in split_file_array:
            total_bytes += os.path.getsize(file_path)
        return total_bytes

    # Adapted from: https://stackoverflow.com/a/14996816/4745097
    @staticmethod
    def human_readable_filesize(num_bytes):
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        i = 0
        while num_bytes >= 1024 and i < len(suffixes) - 1:
            num_bytes /= 1024.
            i += 1
        f = ('%.1f' % num_bytes).rstrip('0').rstrip('.')
        return '%s%s' % (f, suffixes[i])

    @staticmethod
    def detect_compression(abs_path_glob_list):
        env = Utility.get_env_C_locale()
        cat_cmd_list = ["cat"] + abs_path_glob_list
        file_cmd_list = ["file", "--dereference", "--special-files", "-"]
        flat_command_string = Utility.print_cli_friendly("File compression detection ", [cat_cmd_list, file_cmd_list])
        cat_image_process = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE,
                                             env=env,
                                             encoding='utf-8')
        file_utility_process = subprocess.Popen(file_cmd_list, stdin=cat_image_process.stdout,
                                                stdout=subprocess.PIPE, env=env,
                                                encoding='utf-8')
        cat_image_process.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
        stdout, stderr = file_utility_process.communicate()
        if file_utility_process.returncode != 0:
            raise Exception("File utility process had error " + flat_command_string + "\n\n" + str(stderr))
        return Utility.extract_image_compression_from_file_utility(str(stdout))

    # Clonezilla's image has to be detected. The filename only contains the compression for partclone images, but not
    # for the other formats.
    @staticmethod
    def extract_image_compression_from_file_utility(output_of_file_utility_string):
        initial_split = output_of_file_utility_string.split(" ", maxsplit=1)
        if len(initial_split) == 0:
            raise Exception("Unable to detect file compression: " + output_of_file_utility_string)
        elif len(initial_split) == 1:
            raise Exception("Unable to detect file compression: " + output_of_file_utility_string)
        elif len(initial_split) == 2:
            file_output = initial_split[1]
            if file_output.startswith("gzip"):
                # Clonezilla -z1 image compression
                return "gzip"
            elif file_output.startswith("bzip2"):
                # Clonezilla -z2 image compression
                return "bzip2"
            elif file_output.startswith("lzop"):
                # Clonezilla -z3 image compression
                return "lzo"
            elif file_output.startswith("LZMA"):
                # Clonezilla -z4 image compression
                return "lzma"
            elif file_output.startswith("XZ"):
                # Clonezilla -z5 image compression
                return "xz"
            elif file_output.startswith("lzip"):
                # Clonezilla -z6 image compression
                return "lzip"
            elif file_output.startswith("LRZIP"):
                # Clonezilla -z7 image compression
                return "lrzip"
            elif file_output.startswith("LZ4"):
                # Clonezilla -z8 image compression
                return "lz4"
            elif file_output.startswith("Zstandard"):
                # Clonezilla -z9 image compression
                return "zstd"
            elif file_output.startswith("data"):
                # Clonezilla -z0 image (no compression)
                return "uncompressed"
            else:
                # A dd image could produce a file output such as "/dev/stdin: DOS/MBR boot sector; GRand Unified
                # Bootloader, stage1 version 0x79, boot drive 0xbb, stage2 address 0x8e70, 1st sector stage2 0xb8db31c3,
                # stage2 segment 0x201" in which case assuming uncompressed is reasonable.
                print("Unable to detect file compression: " + output_of_file_utility_string + " assuming uncompressed")
                return "uncompressed"
        else:
            raise Exception("Unable to query file compression: " + output_of_file_utility_string)

    @staticmethod
    def get_decompression_command_list(compression_type):
        if compression_type == "gzip":
            return ["pigz", "--decompress", "--stdout"]
        elif compression_type == "bzip2":
            return ["pbzip2", "--decompress", "--stdout"]
        elif compression_type == "lzo":
            return ["lzop", "--decompress", "--stdout"]
        elif compression_type == "lzma":
            return ["unlzma", "--decompress", "--stdout"]
        elif compression_type == "xz":
            return ["unxz", "--stdout"]
        elif compression_type == "lzip":
            return ["plzip", "--decompress", "--stdout"]
        elif compression_type == "lrzip":
            return ["lrzip", "--quiet", "--decompress", "--outfile", "-"]
        elif compression_type == "lz4":
            return ["unlz4", "-d", "-"]
        elif compression_type == "zstd":
            return ["zstd", "--decompress", "--stdout"]
        elif compression_type == "uncompressed":
            # For the uncompressed case, use `cat` utility to pass stdin through to stdout without processing.
            return ["cat", "-"]
        else:
            raise Exception("Unexpected compression: " + compression_type)

    # TODO: Evaluate Clonezilla's ocs-get-comp-suffix function from scripts/sbin/ocs-functions
    # TODO: Simplify logic, maybe combine with other functions
    @staticmethod
    def get_compression_suffix(format):
        if format == "gzip":
            return "gz"
        elif format == "zstd":
            return "zst"
        elif format == "bzip2":
            return "bz2"
        elif format == "uncompressed":
            return "uncomp"
        else:
            raise ValueError("Unknown compression format: " + format)

    # TODO: Simplify logic, maybe combine with other functions
    @staticmethod
    def get_compression_cmd_list(format, level_integer):
        # gzip/pigz/zstd use dash number argument to specify compression level
        level = "-" + str(level_integer)
        if format == "gzip":
            return ["pigz", "--stdout", level]
        elif format == "zstd":
            # Set number of threads to 0 to autodetect number of physical cores
            return ["zstd", "--stdout", level, "--threads=0"]
        elif format == "bzip2":
            return ["pbzip2", "--stdout", level]
        elif format == "uncompressed":
            return ["cat", "-"]
        else:
            raise ValueError("Unknown compression format: " + format)

    @staticmethod
    def schedule_shutdown_reboot(post_task_action):
        if post_task_action == "SHUTDOWN":
            cmd_list = ['shutdown']
            msg = "Shutdown PC"
        elif post_task_action == "REBOOT":
            cmd_list = ['shutdown', '--reboot']
            msg = "Reboot PC"
        else:
            # Do nothing
            return True, ""

        # Run process and don't use the C locale but because the output is displayed to the enduser so translation is
        # useful.
        process, flat_command_string, failed_message = Utility.run(msg, cmd_list, use_c_locale=False)
        if process.returncode == 0:
            # Shutdown command outputs over
            return True, process.stderr
        else:
            return False, "Failed to shutdown: " + failed_message

    # Use ntfsfix to try and mount the partition and if successful clear the "volume dirty" flag, which cancels a
    # scheduled filesystem check for the next boot, among other things.
    #
    # "If the volume cannot be fixed, the dirty volume flag is set to request a volume checking at next mount"
    @staticmethod
    def run_ntfsfix(long_device_node):
        # From man page:
        # "ntfsfix is a utility that fixes some common NTFS problems. ntfsfix is NOT a Linux version of chkdsk.
        # It only repairs some fundamental NTFS inconsistencies, resets the NTFS journal file and schedules an
        # NTFS consistency check for the first boot into Windows."
        process, flat_command_string, failed_message = Utility.run("Run ntfsfix and don't schedule an NTFS consistency check",
                                                   ["ntfsfix", "--clear-dirty", long_device_node], use_c_locale=False)
        if process.returncode != 0:
            return False, failed_message
        return True, ""

    # Query size in bytes of a partition, relevant when partition table may have been recently overwritten invalidating
    # Rescuezilla's existing cache
    @staticmethod
    def query_partition_size_bytes(long_device_node):
        process, flat_command_string, failed_message = Utility.run(
            "Query " + long_device_node,
            ["lsblk", "--bytes", "--noheadings", "--nodeps", "--output", "size", long_device_node],
            use_c_locale=False)
        if process.returncode != 0:
            return False, failed_message
        return True, process.stdout

    # Grow filesystem to fill partition, like Clonezilla's "-r" implemented in sbin/ocs-resize-part
    # TODO: Clonezilla only supports growing filesystems, and shrinking is a key feature which requires
    # TODO: some thought [1]
    # [1] https://github.com/rescuezilla/rescuezilla/issues/18#issuecomment-823057082
    @staticmethod
    def grow_filesystems(filesystem, long_device_node, logger):
        if not os.path.exists(RESCUEZILLA_MOUNT_TMP_DIR) and not os.path.isdir(RESCUEZILLA_MOUNT_TMP_DIR):
            os.mkdir(RESCUEZILLA_MOUNT_TMP_DIR, 0o755)

        is_unmounted, message = Utility.umount_warn_on_busy(RESCUEZILLA_MOUNT_TMP_DIR)
        if not is_unmounted:
            return False, message

        size_in_bytes=""
        # Growing FAT filesystems require quering partition size which other filesystems don't.
        if filesystem == "vfat" or filesystem == "fat16" or filesystem == "fat32":
            is_success, output = Utility.query_partition_size_bytes(long_device_node)
            if not is_success:
                return False, output
            else:
                size_in_bytes = output

        grow_filesystem_dict = {
            'reiserfs': {'match': ["reiserfs"], 'fsck_command': [], 'mount_command': [], 'resize_command': ["resize_reiserfs", "-f", long_device_node]},
            'fat':  {'match': ["vfat", "fat16", "fat32"], 'fsck_command': [], 'mount_command': [], 'resize_command': ["fatresize", "--progress", "--verbose", "--size " + size_in_bytes, long_device_node]},
            'ext':  {'match': ["ext2", "ext3", "ext4"], 'fsck_command': ["e2fsck", "-f", "-y", long_device_node], 'mount_command': [], 'resize_command': ["resize2fs", "-p", long_device_node]},
            # Not using "ntfsfix"
            'ntfs': {'match': ["ntfs"], 'fsck_command': [], 'mount_command': [], 'resize_command': ["ntfsresize", long_device_node]},
            'xfs':  {'match': ["xfs"], 'fsck_command': [], 'mount_command': ["mount", "-t", "xfs", long_device_node, RESCUEZILLA_MOUNT_TMP_DIR], 'resize_command': ["xfs_growfs", long_device_node]},
            'jfs':  {'match': ["jfs"], 'fsck_command': [], 'mount_command': ["mount", "-o", "remount,resize", long_device_node, RESCUEZILLA_MOUNT_TMP_DIR], 'resize_command': []},
            'btrfs':  {'match': ["btrfs"], 'fsck_command': [], 'mount_command': ["mount", "-t", "btrfs", long_device_node, RESCUEZILLA_MOUNT_TMP_DIR], 'resize_command': ["btrfs", "filesystem", "resize", "max", RESCUEZILLA_MOUNT_TMP_DIR]},
            'nilfs2': {'match': ["nilfs2"], 'fsck_command': [], 'mount_command': ["mount", "-t", "nilfs2", long_device_node, RESCUEZILLA_MOUNT_TMP_DIR], 'resize_command': ["nilfs-resize", "--yes", long_device_node]},
        }

        has_found_key = False
        for key in grow_filesystem_dict.keys():
            if filesystem.lower() in grow_filesystem_dict[key]['match']:
                has_found_key = True
                # Found supported filesystem to resize!
                fsck_cmd_list = grow_filesystem_dict[key]['fsck_command']
                if len(fsck_cmd_list) > 0 and shutil.which(fsck_cmd_list[0]) is None:
                    return False, fsck_cmd_list[0] + " not found"
                mount_cmd_list = grow_filesystem_dict[key]['mount_command']
                if len(mount_cmd_list) > 0 and shutil.which(mount_cmd_list[0]) is None:
                    return False, mount_cmd_list[0] + " not found"
                resize_cmd_list = grow_filesystem_dict[key]['resize_command']
                if len(resize_cmd_list) > 0 and shutil.which(resize_cmd_list[0]) is None:
                    return False, resize_cmd_list[0] + " not found"

                combined_identifier = long_device_node + " (" + filesystem + ")"
                if len(fsck_cmd_list) > 0:
                    process, flat_command_string, failed_message = Utility.run("Running filesystem check " + combined_identifier,
                                                                               fsck_cmd_list, use_c_locale=False, logger=logger)
                    if process.returncode != 0:
                        return False, failed_message
                if len(mount_cmd_list) > 0:
                    process, flat_command_string, failed_message = Utility.run("Mounting " + combined_identifier, mount_cmd_list, use_c_locale=False, logger=logger)
                    if process.returncode != 0:
                        return False, failed_message
                if len(resize_cmd_list) > 0:
                    resize_process, resize_flat_command_string, resize_failed_message = Utility.run("Growing filesytem " + combined_identifier, resize_cmd_list, use_c_locale=False, logger=logger)
                    # Always umount, even on resize failure
                    if len(mount_cmd_list) > 0:
                        umount_process, umount_flat_command_string, umount_failed_message = Utility.run("Umounting " + combined_identifier, ["umount", long_device_node], use_c_locale=False, logger=logger)
                    if resize_process.returncode != 0:
                        # Return the resize failed message
                        return False, resize_failed_message
                # Unmount even if the resize_command is empty (eg, the JFS case)
                if len(mount_cmd_list) > 0:
                    process, flat_command_string, failed_message = Utility.run(
                    "Umount " + long_device_node, ["umount", long_device_node], use_c_locale=False, logger=logger)
                    if process.returncode != 0:
                        return False, failed_message

        if not has_found_key:
            print("Unable to resize " + long_device_node + " " + filesystem)
        return True, ""

    @staticmethod
    def get_combobox_key(combobox):
        tree_iter = combobox.get_active_iter()
        if tree_iter is not None:
            model = combobox.get_model()
            combobox_key, = model[tree_iter][:1]
            return combobox_key
        else:
            raise ValueError("Could not get combobox key")

    # TODO: Find better place for this
    @staticmethod
    def get_cannot_distinguish_msg():
        return _("Note: This image format cannot distinguish between failed partclone backup and a user who chose not to backup a partition.")

    # Options for partclone to ignore filesystem inconsistencies, bad sectors and other drive read errors
    # [1] https://github.com/rescuezilla/rescuezilla/issues/237
    @staticmethod
    def get_partclone_rescue_options(is_rescue):
        if is_rescue:
            return ["--force", "--rescue"]
        else:
            return []
