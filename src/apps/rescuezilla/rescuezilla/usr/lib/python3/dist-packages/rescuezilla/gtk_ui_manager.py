from typing import List, Optional, Callable, Any, Tuple

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GObject
from ui_manager import UiManager
from utility import Utility, ErrorMessageModalPopup

"""
Graphical version of (command-line interface) UIManager class.
Super functions called to write out debug messages to stdout
"""
# TODO: Switch the public interface to simply passthrough arguments to the on-UI-thread private interface
# TODO: using *args/**kwargs, to avoid the violation of the Don't Repeat Yourself principle.
class GtkUiManager(UiManager):
    def __init__(self,
                 builder: GObject,
                 main_statusbar: GObject,
                 main_statusbar_context_id: str,
                 progress_bars: List[Any],
                 progress_statuses: List[Any],
                 post_task_action_combobox: Optional[Any],
                 summary_program_defined_texts: List[Any]):
        super().__init__()
        self.builder: GObject = builder
        self.main_statusbar: GObject = main_statusbar
        self.main_statusbar_context_id = main_statusbar_context_id
        self.progress_bars: List[GObject] = progress_bars
        self.progress_statuses: List[GObject] = progress_statuses
        self.post_task_action_combobox: Optional[GObject] = post_task_action_combobox
        self.summary_program_defined_texts: List[GObject] = summary_program_defined_texts

    def update_progress_bar(self,
                            fraction: float):
        super().update_progress_bar(fraction=fraction)
        GLib.idle_add(self._update_progress_bar, fraction)

    def _update_progress_bar(self,
                             fraction: float):
        if self.logger is not None:
            self.logger.write("Updating progress bar to " + str(fraction))
        for progress_bar in self.progress_bars:
            progress_bar.set_fraction(fraction)

    def update_progress_status(self,
                               message: str):
        super().update_progress_status(message=message)
        GLib.idle_add(self._update_progress_status, message)

    def _update_progress_status(self, message):
        for progress_status in self.progress_statuses:
            progress_status.set_text(message)

    # Intended to be called via event thread
    def get_post_task_action(self) -> str:
        # No need to call super here
        return Utility.get_combobox_key(self.post_task_action_combobox)

    def update_main_statusbar(self,
                              message: str):
        super().update_main_statusbar(message=message)
        GLib.idle_add(self._update_main_statusbar, message)

    def _update_main_statusbar(self,
                               message: str):
        context_id = self.main_statusbar.get_context_id(self.main_statusbar_context_id)
        self.main_statusbar.pop(context_id)
        self.main_statusbar.push(context_id, message)

    def display_status(self,
                       msg1: str,
                       msg2: str):
        super().display_status(msg1=msg1, msg2=msg2)
        GLib.idle_add(self._display_status, msg1, msg2)

    def _display_status(self, msg1, msg2):
        self.update_progress_status(message=msg1 + "\n" + msg2)
        if msg2 != "":
            status_bar_msg = msg1 + ": " + msg2
        else:
            status_bar_msg = msg1
        # Call private member directly, as already on GTK thread
        self._update_main_statusbar(message=status_bar_msg)

    def remove_all_main_statusbar(self,
                                  context_id: str):
        GLib.idle_add(self._remove_all_main_statusbar, context_id)

    def _remove_all_main_statusbar(self,
                                   context_id: str):
        self.main_statusbar.remove_all(self.main_statusbar.get_context_id(context_id))

    def display_error_message(self,
                              summary_message: str,
                              heading: str = ""):
        GLib.idle_add(self._display_error_message, summary_message, heading)

    def _display_error_message(self,
                               summary_message: str,
                               heading: str = ""):
        ErrorMessageModalPopup(self.builder,
                               error_content=summary_message,
                               error_heading=heading)

    def completed_operation(self,
                            callable_fn: Callable,
                            succeeded: bool,
                            message: str) -> Tuple[bool, str]:
        GLib.idle_add(self._completed_operation, callable_fn, succeeded, message)
        return succeeded, message

    def _completed_operation(self,
                             callable_fn: Callable,
                             succeeded: bool,
                             message: str):
        callable_fn(succeeded=succeeded, message=message)

    def escape_text(self, input: str) -> str:
        return GObject.markup_escape_text(input)

    def display_summary_text(self, text_to_display):
        for summary_program_defined_text in self.summary_program_defined_texts:
            summary_program_defined_text.set_markup(text_to_display)
