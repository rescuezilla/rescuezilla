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
import threading
import traceback
from datetime import datetime
from time import sleep

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, GLib

from logger import Logger
from parser.clonezilla_image import ClonezillaImage
from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import ErrorMessageModalPopup, Utility, _


# Signals should automatically propagate to processes called with subprocess.run().

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

    def start_verify(self, image, completed_callback):
        self.verify_timestart = datetime.now()
        self.image = image
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
        self.completed_verify(False, _("Restore cancelled by user."))

    def do_verify_wrapper(self):
        try:
            self.do_verify()
        except Exception as exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            GLib.idle_add(self.completed_verify, False, _("Error restoring image: ") + tb)
            return

    def do_verify(self):
        self.requested_stop = False

        # Clear proc dictionary
        self.proc.clear()
        self.summary_message_lock = threading.Lock()
        self.summary_message = ""
        env = Utility.get_env_C_locale()

        self.logger = Logger("/tmp/rescuezilla.log." + datetime.now().strftime("%Y%m%dT%H%M%S") + ".txt")
        GLib.idle_add(self.update_progress_bar, 0)

        with self.summary_message_lock:
            self.summary_message += self.image.absolute_path + "\n"

        for i in range(1, 10):
            sleep(2)
            GLib.idle_add(self.update_progress_bar, (i*10) / 100.0)

        if isinstance(self.image, ClonezillaImage):
            self.logger.write("Detected ClonezillaImage")
            image_dir = os.path.dirname(self.image.absolute_path)
            # TODO: Handle multidisk Clonezilla images
            short_selected_image_drive_node = self.image.short_device_node_disk_list[0]
            if self.requested_stop:
                GLib.idle_add(self.completed_verify, False, _("User requested operation to stop."))
                return
        elif isinstance(self.image, RedoBackupLegacyImage):
            self.logger.write("Detected RedoBackupLegacyImage")
        GLib.idle_add(self.completed_verify, True, "")
        return

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
        duration_minutes = (verify_timeend - self.verify_timestart).total_seconds() / 60.0

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
            self.summary_message += "\n" + _("Operation took {num_minutes} minutes.").format(num_minutes=duration_minutes) + "\n"
        self.populate_summary_page()
        self.logger.close()
        self.completed_callback(succeeded)

    def populate_summary_page(self):
        with self.summary_message_lock:
            self.logger.write("Populating summary page with:\n\n" + self.summary_message)
            text_to_display = _("""<b>{heading}</b>

{message}""").format(heading=_("Verification Summary"), message=GObject.markup_escape_text(self.summary_message))
        self.builder.get_object("verify_step4_summary_program_defined_text").set_markup(text_to_display)
