# ----------------------------------------------------------------------
#   Copyright (C) 2019-2023 Rescuezilla.com <rescuezilla@gmail.com>
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

from typing import Optional, Callable, Tuple

from logger import Logger

"""
Quick Duck-typed wrapper for Gtk commands, to enable command-line interface

Beware of minor gotcha: GLib.idle_add() doesn't appear to like keyworded args (**kwargs), so the public and private API
split between the base (CLI) UI class and the child GUI UI class has taken care taken to use list type args (including
with **args).
"""

class UiManager:
    def __init__(self):
        self.logger: Optional[Logger] = None

    def set_logger(self, logger: Logger):
        self.logger = logger

    def update_progress_bar(self,
                            fraction: float):
        if self.logger is not None:
            self.logger.write("Updating progress bar to " + str(fraction))
        else:
            print(f"{fraction} ")

    def update_progress_status(self,
                               message: str):
        if self.logger is not None:
            self.logger.write(message)
        else:
            print(message)

    # Intended to be called via event thread
    def get_post_task_action(self) -> str:
        return "DO_NOTHING"

    def update_main_statusbar(self,
                              message: str):
        if self.logger is not None:
            self.logger.write(message)
        else:
            print(message)

    def display_status(self,
                       msg1: str,
                       msg2: str):
        if msg2 != "":
            message = msg1 + ": " + msg2
        else:
            message = msg1
        if self.logger is not None:
            self.logger.write(message)

    def remove_all_main_statusbar(self,
                                  context_id: str):
        return

    def display_error_message(self, summary_message: str, heading: str = ""):
        if self.logger is not None:
            self.logger.write(summary_message)
        else:
            print(summary_message)

    def completed_operation(self,
                             callable_fn: Callable,
                             succeeded: bool,
                             message: str) -> Tuple[bool, str]:
        callable_fn(succeeded=succeeded, message=message)
        return succeeded, message

    # TODO: Better abstract from handler.py
    def _on_operation_completed_callback(self, is_success):
        pass

    def escape_text(self, input: str) -> str:
        # No need to escape GTK text for CLI
        return input

    def display_summary_text(self, text_to_display):
        if self.logger is not None:
            self.logger.write(text_to_display)
        else:
            print(text_to_display)
