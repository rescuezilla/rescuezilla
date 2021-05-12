# ----------------------------------------------------------------------
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
import sys
import threading

class Logger:
    # Logger to help debugging.
    #
    # Class based on answer: https://stackoverflow.com/a/24583265/4745097
    def __init__(self, output_filepath):
        # Threading note: This class is expected to be called on both GTK event thread
        # and other threads. Whilst I believe stdout and file write operations have threading
        # guarantees internally, a threading.lock is used just in case this is not true.
        #
        # TODO: Evaluate whether this threading.Lock() is required.
        self.logger_lock = threading.Lock()
        self.stdout = sys.stdout
        self.file = open(output_filepath, "a", 10)
        sys.stdout = self

    def __del__(self):
        self.close()

    def __exit__(self, *args):
        self.close()

    def write(self, message):
        with self.logger_lock:
            if self.stdout is not None:
                self.stdout.write(message)
            try:
                self.file.write(message)
            except:
                print("Could not write log message to file: " + message)

    def close(self):
        with self.logger_lock:
            if self.stdout is not None:
                sys.stdout = self.stdout
                self.stdout = None

            if self.file is not None:
                self.file.close()
                self.file = None

    def flush(self):
        with self.logger_lock:
            self.stdout.flush()
            self.file.flush()
            os.fsync(self.file.fileno())
