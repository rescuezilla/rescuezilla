# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
#   Copyright (C) 2003-2020 Steven Shiau <steven _at_ clonezilla org>
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
import gettext
import os
import pwd
import re
import subprocess
from queue import Queue
from threading import Thread
from time import sleep

import gi

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


class ErrorMessageModalPopup:
    def __init__(self, builder, message):
        print("Displaying error box: " + message)
        self._main_window = builder.get_object("main_window")
        self._dialog = Gtk.MessageDialog(parent=self._main_window, type=Gtk.MessageType.ERROR,
                                         buttons=Gtk.ButtonsType.OK,
                                         message_format=message)
        # Ensure user can copy and paste dialog messages
        for child in self._dialog.get_message_area().get_children():
            child.set_selectable(True)
        self._dialog.vbox.set_margin_left(30)
        self._dialog.vbox.set_margin_right(30)
        self._dialog.vbox.set_margin_bottom(15)

        self._dialog.connect("response", self._response)
        self._main_window.set_sensitive(False)
        self._dialog.set_keep_above(True)
        self._dialog.show()

    """ Close the window on clicking the 'OK' button """

    def _response(self, response_id, user_param1):
        self._main_window.set_sensitive(True)
        self._dialog.destroy()

    @staticmethod
    def display_nonfatal_warning_message(builder, message):
        print(message)
        ErrorMessageModalPopup(builder, message)


class AreYouSureModalPopup:
    def __init__(self, builder, message, callback):
        self._main_window = builder.get_object("main_window")
        self._dialog = Gtk.MessageDialog(parent=self._main_window, type=Gtk.MessageType.ERROR,
                                         buttons=Gtk.ButtonsType.YES_NO, message_format=message)
        # Ensure user can copy and paste dialog messages
        for child in self._dialog.get_message_area().get_children():
           child.set_selectable(True)
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


class FolderSelectionPopup:
    def __init__(self, builder, callback, default_directory, is_allow_selecting_folder_outside_mount):
        self._main_window = builder.get_object("main_window")
        #FIXME: Make this a validator
        self.is_allow_selecting_folder_outside_mount = is_allow_selecting_folder_outside_mount
        # Label to update with the selected folder
        self._dialog = Gtk.FileChooserDialog(parent=self._main_window, action=Gtk.FileChooserAction.SELECT_FOLDER,
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
    # Background: The Rescuezilla frontend uses PolKit to elevate from the standard user to root user, as is required to
    # access harddrive block devices. To open graphical tools from an application running as root as a non-privileged
    # user requires this wrapper.
    @staticmethod
    def open_app_as_target_user(target_user, process_list):
        current_user = pwd.getpwuid(os.getuid()).pw_name
        print("Current user is '" + current_user + "'. As user '" + target_user + "' launching: " + str(process_list))
        try:
            pwd.getpwnam(target_user)
            does_target_user_exists = True
        except KeyError:
            print("Launching app " + str(process_list) + " as non-root user failed. Target user: " + target_user + " does not not exist.")
            return

        if does_target_user_exists:
            # Launch detached subprocess as target user
            sudo_process_list = ["sudo", "-u", target_user] + process_list
            subprocess.Popen(sudo_process_list, start_new_session=True)
        return

    # Opens URL in web browser using non-root user, for users that need to click on a link within the Rescuezilla
    # frontend (eg, to access the Rescuezilla forum to receive support).
    # Clicking on a URL within Rescuezilla using a GTK LinkButton attempts to open a web
    # browser as root user (which modern web browsers do not allow). Fortunately most end-users will be running the X
    # Windowing System session as a non-root user,
    @staticmethod
    def open_url_as_non_root(target_user, url):
        # Default web browser symlink as configured by the Debian Alternatives System configured web browser.
        Utility.open_app_as_target_user(target_user, ["x-www-browser", url])

    @staticmethod
    def open_path_in_filemanager_as_non_root(target_user, path):
        # TODO: Handle file managers other than pcmanfm
        Utility.open_app_as_target_user(target_user, ["pcmanfm", path])

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
    def print_cli_friendly(message, cmd_list_list):
        print(message + ". Running: ", end="")
        flat_command_string = ""
        i = 0
        for cmd_list in cmd_list_list:
            for cmd in cmd_list:
                flat_command_string += cmd + " "
            i += 1
            if i < len(cmd_list_list):
                flat_command_string += "| "
        # Print newline to flush the buffer
        print(flat_command_string)
        return flat_command_string

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

        # This communicate should return immediately.
        stdout_data, stderr_data = process.communicate()
        logging_output = short_description + ": " + flat_command_string + " returned " + str(
            process.returncode) + ": " + stdout_data + "\n"
        print(logging_output)

        fail_description = _("Failed to run command: ") + flat_command_string + "\n\n" + stdout_data + "\n\n"
        return process, flat_command_string, fail_description

    @staticmethod
    def run_external_command(cmd_list, fail_callback, env):
        Utility.print_cli_friendly(cmd_list[0], [cmd_list, ])
        process = subprocess.run(cmd_list, encoding='utf-8', capture_output=True, env=env)
        if process.returncode != 0:
            error_message = "Error running " + cmd_list[0]
            print(error_message)
            GLib.idle_add(fail_callback, False, error_message + ": " + process.stderr)
            return
        print("stdout: " + process.stdout + " stderr " + process.stderr)
        return process.stdout, process.stderr, process.returncode

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

    # Simple method to get the total percentage progress ratio.
    # TODO: Use the partition total bytes, rather than simply the number of partitions
    @staticmethod
    def calculate_progress_ratio(current_partition_percentage, image_number, total_partitions):
        return current_partition_percentage / total_partitions + (image_number - 1) / total_partitions

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