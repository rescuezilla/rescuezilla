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
import copy
import threading
import traceback

import gi

from parser.apart_gtk_image import ApartGtkImage
from parser.fogproject_image import FogProjectImage
from parser.foxclone_image import FoxcloneImage
from parser.fsarchiver_image import FsArchiverImage
from parser.metadata_only_image import MetadataOnlyImage
from parser.redorescue_image import RedoRescueImage
from wizard_state import Mode

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, GLib

from parser.clonezilla_image import ClonezillaImage
from parser.combined_drive_state import CombinedDriveState
from parser.lvm import Lvm
from parser.redobackup_legacy_image import RedoBackupLegacyImage
from utility import Utility, ErrorMessageModalPopup, _, PleaseWaitModalPopup

# FIXME: The LVM handling in this class could be vastly improved.
# FIXME: Better reset state when pressing Back/Next buttons, especially around the 'overwrite partition table' checkbox.
class PartitionsToRestore:
    def __init__(self, builder):
        self.builder = builder
        self.destination_partition_combobox_list = self.builder.get_object("destination_partition_combobox_list")

        self.NOT_RESTORING_PARTITION_KEY = "DISABLED"
        self.NOT_RESTORING_PARTITION_ENDUSER_FRIENDLY = _("Not restoring this partition")
        self.win = self.builder.get_object("main_window")

        self.overwriting_partition_table_message = "<b>" + _("You will be overwriting the partition table.") + "</b>"
        self.not_overwriting_partition_table_message = _("You will <b>not</b> be overwriting the partition table.")
        self.no_partition_table_message = _("The source does not contain a partition table.")

        self.lvm_lv_path_list = []
        self.lvm_lv_path_lock = threading.Lock()

        # FIXME: Refactor the code to remove the need for this ugly initialization.
        self.dest_drive_dict = {"partitions": {}}

        self.mode_list = [Mode.RESTORE, Mode.CLONE]
        self.partition_table_checkbutton_dict = {Mode.RESTORE: self.builder.get_object("restore_overwrite_partition_table_checkbutton"),
                                                 Mode.CLONE: self.builder.get_object("clone_overwrite_partition_table_checkbutton")}
        self.overwrite_partition_table_warning_label_dict = {Mode.RESTORE: self.builder.get_object("restore_step4_overwrite_partition_table_warning_label"),
                                                             Mode.CLONE: self.builder.get_object("clone_step4_overwrite_partition_table_warning_label")}
        self.selected_image_text_dict = {Mode.RESTORE: self.builder.get_object("restore_step4_selected_image_text"),
                                                             Mode.CLONE: self.builder.get_object("clone_step4_selected_drives_text")}
        self.partition_selection_list = self.builder.get_object("partition_selection_list")
        self.destination_partition_combobox_cell_renderer_dict = {Mode.RESTORE: self.builder.get_object("restore_destination_partition_combobox_cell_renderer"),
                                                             Mode.CLONE: self.builder.get_object("clone_destination_partition_combobox_cell_renderer")}

        self.selected_image = None
        self.please_wait_popup = None
        self.dest_drive_key = ""
        self.dest_drive_node = {}

    def set_overwriting_partition_warning_label(self, is_overwriting):
        if is_overwriting:
            for mode in self.mode_list:
                overwrite_partition_table_warning_text = self.overwriting_partition_table_message + " " + _("The \"destination partition\" column has been updated using the information stored within the backup image.\n\n<b>If partitions have been resized, new partitions added, or additional operating systems installed <i>since the backup image was created</i>, then the destination drive's partition table will not match the backup image, and overwriting the destination drive's partition table will render these resized and additional partitions permanently inaccessible.</b> If you have not modified the partition table in such a way since creating this backup then overwriting the partition table is completely safe and will have no negative effects.")
                self.overwrite_partition_table_warning_label_dict[mode].set_markup(overwrite_partition_table_warning_text)
            self._use_image_partition_table()
        else:
            pt_warning = self.not_overwriting_partition_table_message
            if not self.selected_image.has_partition_table():
                pt_warning = self.no_partition_table_message
            target_node_warning_text = pt_warning + " " + _("The \"destination partition\" column has been updated with destination drive's existing partition table information.\n\n<b>The destination partition column can be modified as a dropdown menu. Incorrectly mapping the destination partitions may cause operating systems to no longer boot.</b> If you are unsure of the mapping, consider if it's more suitable to instead overwrite the partition table.")
            for mode in self.mode_list:
                self.overwrite_partition_table_warning_label_dict[mode].set_markup(target_node_warning_text)
            self._use_existing_drive_partition_table()

    def initialize_individual_partition_restore_list(self, selected_image, dest_drive_node, dest_drive_desc,
                                                     dest_drive_dict):
        self.selected_image = selected_image
        self.dest_drive_node = dest_drive_node
        self.dest_drive_desc = dest_drive_desc
        self.dest_drive_dict = dest_drive_dict

        if isinstance(self.selected_image, ClonezillaImage):
            print("Got selected Clonezilla image: " + str(selected_image.image_format_dict_dict))
        elif isinstance(self.selected_image, RedoBackupLegacyImage):
            print("Got selected RedoBackupLegacy image: " + str(selected_image.normalized_sfdisk_dict))
        self._use_image_partition_table()

        info_string = "<b>" + _("Selected image") + "</b> " + GObject.markup_escape_text(self.selected_image.absolute_path) + "\n" + "<b>" + _("Destination device") + "</b> " + GObject.markup_escape_text(self.dest_drive_desc)
        for mode in self.mode_list:
            self.selected_image_text_dict[mode].set_markup(info_string)

        print("Have selected image " + str(self.selected_image))
        print("Have drive dict " + str(self.dest_drive_dict))

        # If the image has a partition table, the overwrite toggle is enabled and defaults to True. Otherwise
        # it's not possible to overwrite the partition table.
        for overwrite_partition_table_checkbutton in self.partition_table_checkbutton_dict.values():
            overwrite_partition_table_checkbutton.set_sensitive(self.selected_image.has_partition_table())
            overwrite_partition_table_checkbutton.set_active(self.selected_image.has_partition_table())
        self.set_overwriting_partition_warning_label(self.selected_image.has_partition_table())

    # Starts LVM and umounts all relevant logical volumes
    # FIXME: Similar code is is duplicated elsewhere in the codebase.
    def _scan_and_unmount_existing_lvm(self, dest_partitions, is_overwriting_partition_table):
        with self.lvm_lv_path_lock:
            self.lvm_lv_path_list.clear()

        error_message = ""
        try:
            # Gathering LVM logical volumes.
            # Start the Logical Volume Manager (LVM). Caller raises Exception on failure
            Lvm.start_lvm2(logger=None)
            vg_state_dict = Lvm.get_volume_group_state_dict(logger=None)

            for dest_partition_key in dest_partitions:
                # Figure out LVM Volume Groups and Logical Volumes
                relevant_vg_name_list = []
                for report_dict in vg_state_dict['report']:
                    for vg_dict in report_dict['vg']:
                        if 'pv_name' in vg_dict.keys() and dest_partition_key == vg_dict['pv_name']:
                            if 'vg_name' in vg_dict.keys():
                                vg_name = vg_dict['vg_name']
                            else:
                                error_message += "Could not find volume group name vg_name in " + str(vg_dict) + "\n"
                                # TODO: Re-evaluate how exactly Clonezilla uses /NOT_FOUND and whether introducing it here
                                # TODO: could improve Rescuezilla/Clonezilla interoperability.
                                continue
                            if 'pv_uuid' in vg_dict.keys():
                                pv_uuid = vg_dict['pv_uuid']
                            else:
                                error_message += "Could not find physical volume UUID pv_uuid in " + str(vg_dict) + "\n"
                                continue
                            relevant_vg_name_list.append(vg_name)
                lv_state_dict = Lvm.get_logical_volume_state_dict(logger=None)
                for report_dict in lv_state_dict['report']:
                    for lv_dict in report_dict['lv']:
                        # Only consider VGs that match the partitions to backup list
                        if 'vg_name' in lv_dict.keys() and lv_dict['vg_name'] in relevant_vg_name_list:
                            vg_name = lv_dict['vg_name']
                            if 'lv_path' in lv_dict.keys():
                                lv_path = lv_dict['lv_path']
                                is_unmounted, message = Utility.umount_warn_on_busy(lv_path)
                                if not is_unmounted:
                                    error_message += message
                                else:
                                    # TODO: Make this logic better
                                    with self.lvm_lv_path_lock:
                                        self.lvm_lv_path_list.append(lv_path)
                            else:
                                continue

            # Stop the Logical Volume Manager (LVM)
            failed_logical_volume_list, failed_volume_group_list = Lvm.shutdown_lvm2(self.builder, None)
            for failed_volume_group in failed_volume_group_list:
                error_message += "Failed to shutdown Logical Volume Manager (LVM) Volume Group (VG): " + failed_volume_group[
                    0] + "\n\n" + failed_volume_group[1]
                GLib.idle_add(self.post_lvm_preparation, is_overwriting_partition_table, False, error_message)
                return

            for failed_logical_volume in failed_logical_volume_list:
                error_message += "Failed to shutdown Logical Volume Manager (LVM) Logical Volume (LV): " + \
                          failed_logical_volume[0] + "\n\n" + failed_logical_volume[1]
                GLib.idle_add(self.post_lvm_preparation, is_overwriting_partition_table, False, error_message)
                return
            GLib.idle_add(self.post_lvm_preparation, is_overwriting_partition_table, True, error_message)
        except Exception as e:
            tb = traceback.format_exc()
            traceback.print_exc()
            message = "Unable to process Logical Volume Manager (LVMs): " + tb
            GLib.idle_add(self.post_lvm_preparation, is_overwriting_partition_table, False, error_message)
        GLib.idle_add(self.post_lvm_preparation, is_overwriting_partition_table, True, error_message)

    def overwrite_partition_table_toggle(self, is_overwriting_partition_table):
        print("Overwrite partition table toggle changed to " + str(is_overwriting_partition_table))
        if is_overwriting_partition_table:
            # Don't need to scan for existing LVM logical volumes when overwriting partition table.
            self.post_lvm_preparation(is_overwriting_partition_table, True, "")
        else:
            self.win.set_sensitive(False)
            # Protect against accidentally overwriting the please_wait_popup reference when the checkbox is toggled
            # FIXME: Improve logic so this is not required
            if self.please_wait_popup is not None:
                self.please_wait_popup.destroy()
                self.please_wait_popup = None
            self.please_wait_popup = PleaseWaitModalPopup(self.builder, title=_("Please wait..."), message=_("Scanning and unmounting any Logical Volume Manager (LVM) Logical Volumes..."))
            self.please_wait_popup.show()
            if 'partitions' in self.dest_drive_dict.keys():
                partitions = self.dest_drive_dict['partitions']
            else:
                # TODO: Make this logic better.
                partitions = self.dest_drive_dict
            thread = threading.Thread(target=self._scan_and_unmount_existing_lvm, args=[copy.deepcopy(partitions).keys(), is_overwriting_partition_table])
            thread.daemon = True
            thread.start()

    def post_lvm_preparation(self, is_overwriting_partition_table, is_lvm_shutdown_success, lvm_error_message):
        if self.please_wait_popup is not None:
            self.please_wait_popup.destroy()
            self.please_wait_popup = None

        if not is_lvm_shutdown_success or len(lvm_error_message) != 0:
            error = ErrorMessageModalPopup(self.builder, lvm_error_message)
            # Ensure that the overwrite partition table button stays checked.
            is_overwriting_partition_table = True
            for overwrite_partition_table_checkbutton in self.partition_table_checkbutton_dict:
                overwrite_partition_table_checkbutton.set_sensitive(self.selected_image.has_partition_table())
                overwrite_partition_table_checkbutton.set_active(self.selected_image.has_partition_table())

        self.set_overwriting_partition_warning_label(is_overwriting_partition_table)
        for mode in self.mode_list:
            self.destination_partition_combobox_cell_renderer_dict[mode].set_sensitive(not is_overwriting_partition_table)

    def change_combo_box(self, path_string, target_node_string, enduser_friendly_string):
        print(
            "Changing the combobox on row " + path_string + " to " + target_node_string + " / " + enduser_friendly_string)
        liststore_iter = self.partition_selection_list.get_iter(path_string)

        self._swap_destination_partition_node_with_backup(liststore_iter)
        self.partition_selection_list.set_value(liststore_iter, 3, target_node_string)
        self.partition_selection_list.set_value(liststore_iter, 4, enduser_friendly_string)
        # Automatically tick the restore checkbox
        self.partition_selection_list.set_value(liststore_iter, 1, True)

    def toggle_restore_of_row(self, iter, new_toggle_state):
        # Need to be able to disable restore of individual partitions.

        is_empty_dest_partition = False
        if self.partition_selection_list.get_value(iter, 5) == self.NOT_RESTORING_PARTITION_KEY:
            is_empty_dest_partition = True
        if new_toggle_state and is_empty_dest_partition:
            print("Blocking enabling the toggle when the destination partition is not set")
            error = ErrorMessageModalPopup(self.builder,
                                           _("No destination partition selected. Use the destination partition drop-down menu to select the destination"))
            return

        # Update the underlying model to ensure the checkbox will reflect the new state
        self.partition_selection_list.set_value(iter, 1, new_toggle_state)
        self._swap_destination_partition_node_with_backup(iter)
        # If the row has been disabled, update the combobox
        if not new_toggle_state:
            self.partition_selection_list.set_value(iter, 3, self.NOT_RESTORING_PARTITION_KEY)
            self.partition_selection_list.set_value(iter, 4, self.NOT_RESTORING_PARTITION_ENDUSER_FRIENDLY)

    def _use_image_partition_table(self):
        # Populate image partition list
        self.destination_partition_combobox_list.clear()
        self.partition_selection_list.clear()
        if isinstance(self.selected_image, ClonezillaImage) or isinstance(self.selected_image, RedoBackupLegacyImage) or \
                isinstance(self.selected_image, FogProjectImage) or isinstance(self.selected_image, RedoRescueImage) or \
                isinstance(self.selected_image, FoxcloneImage) or isinstance(self.selected_image, MetadataOnlyImage):
            for image_format_dict_key in self.selected_image.image_format_dict_dict.keys():
                print("ClonezillaImage contains partition " + image_format_dict_key)
                if self.selected_image.does_image_key_belong_to_device(image_format_dict_key):
                    if self.selected_image.image_format_dict_dict[image_format_dict_key]['is_lvm_logical_volume']:
                        # The destination of an LVM logical volume within a partition (eg /dev/cl/root) is unchanged
                        dest_partition = self.selected_image.image_format_dict_dict[image_format_dict_key][
                            'logical_volume_long_device_node']
                        flat_description = "Logical Volume " + image_format_dict_key + ": " + self.selected_image.flatten_partition_string(image_format_dict_key)
                    else:
                        # The destination partition of a regular partition in the image (eg, /dev/sda4) is dependent on
                        # the destination drive node (eg /dev/sdb) so we need to split and join the device so the
                        # mapping correctly reads "/dev/sdb4".
                        image_base_device_node, image_partition_number = Utility.split_device_string(image_format_dict_key)
                        # Combine image partition number with destination device node base
                        dest_partition = Utility.join_device_string(self.dest_drive_node, image_partition_number)
                        flat_description = _("Partition {partition_number}").format(partition_number=str(
                            image_partition_number)) + ": " + self.selected_image.flatten_partition_string(image_format_dict_key)
                    self.destination_partition_combobox_list.append([dest_partition, flat_description])
                    self.partition_selection_list.append(
                        [image_format_dict_key, True, flat_description, dest_partition, flat_description,
                         dest_partition, flat_description])
        elif isinstance(self.selected_image, FsArchiverImage):
            # Doesn't appear that FsArchiver images ever have an partition table backup associated with it. But
            # keeping this section for reference, especially if a frontend like qt-fsarchiver adds partition table
            # backups.
            for fs_key in self.selected_image.fsa_dict['filesystems'].keys():
                long_device_node = self.selected_image.fsa_dict['filesystems'][fs_key]['original_long_device_node']
                image_base_device_node, image_partition_number = Utility.split_device_string(long_device_node)
                # Combine image partition number with destination device node base
                dest_partition = Utility.join_device_string(self.dest_drive_node, image_partition_number)
                flat_description = _("Partition {partition_number}").format(partition_number=str(
                    image_partition_number)) + " (" + dest_partition + "): " + self.selected_image.flatten_partition_string(
                    fs_key)
                self.destination_partition_combobox_list.append([dest_partition, flat_description])
                self.partition_selection_list.append(
                    [fs_key, True, flat_description, dest_partition, flat_description, dest_partition,
                     flat_description])
        elif isinstance(self.selected_image, ApartGtkImage):
            # Shouldn't be called because ApartGTK images don't have a partition table
            print("Error: Images created with apart-gtk don't have partition tables")

        for mode in self.mode_list:
            self.destination_partition_combobox_cell_renderer_dict[mode].set_sensitive(False)

    def _use_existing_drive_partition_table(self):
        self.destination_partition_combobox_list.clear()
        self.partition_selection_list.clear()

        num_destination_partitions = 0

        with self.lvm_lv_path_lock:
            for lvm_lv_path in self.lvm_lv_path_list:
                self.destination_partition_combobox_list.append([lvm_lv_path, "Logical Volume: " + lvm_lv_path])
                num_destination_partitions += 1

        print("Looking at " + str(self.selected_image) + " and " + str(self.dest_drive_dict))

        # For the safety of end-users, ensure the initial combobox mapping is blank. It's possible to autogenerate a
        # mapping, but this could be wrong so far simpler for now to leave the mapping blank and rely on end-user
        # decisions.
        flattened_part_description = self.NOT_RESTORING_PARTITION_ENDUSER_FRIENDLY
        dest_partition_key = self.NOT_RESTORING_PARTITION_KEY
        is_restoring_partition = False

        # Populate image partition selection list (left-hand side column)
        if isinstance(self.selected_image, ClonezillaImage) or isinstance(self.selected_image, RedoBackupLegacyImage) or \
                isinstance(self.selected_image, FogProjectImage) or isinstance(self.selected_image, RedoRescueImage) or \
                isinstance(self.selected_image, FoxcloneImage) or isinstance(self.selected_image, ApartGtkImage) or \
                isinstance(self.selected_image, MetadataOnlyImage):
            for image_format_dict_key in self.selected_image.image_format_dict_dict.keys():
                if self.selected_image.does_image_key_belong_to_device(image_format_dict_key):
                    if self.selected_image.image_format_dict_dict[image_format_dict_key]['is_lvm_logical_volume']:
                        flat_image_part_description = "Logical Volume " + image_format_dict_key + ": "\
                                                      + self.selected_image.flatten_partition_string(image_format_dict_key)
                    elif isinstance(self.selected_image, ApartGtkImage):
                        # ApartGtkImage may contain multiple partitions, so the key contains the timestamp too. Therefore
                        # need to make sure the split device string function doesn't get called
                        flat_image_part_description = image_format_dict_key + ": "\
                                                      + self.selected_image.flatten_partition_string(image_format_dict_key)
                    else:
                        image_base_device_node, image_partition_number = Utility.split_device_string(image_format_dict_key)
                        flat_image_part_description = _("Partition {partition_number}").format(partition_number=str(
                    image_partition_number)) + ": "\
                                                      + self.selected_image.flatten_partition_string(image_format_dict_key)
                    self.partition_selection_list.append(
                        [image_format_dict_key, is_restoring_partition, flat_image_part_description, dest_partition_key,
                         flattened_part_description,
                         dest_partition_key, flattened_part_description])
                    num_destination_partitions += 1
        elif isinstance(self.selected_image, FsArchiverImage):
            for fs_key in self.selected_image.fsa_dict['filesystems'].keys():
                flat_image_part_description = "Filesystem " + str(
                fs_key) + ": " + self.selected_image.flatten_partition_string(fs_key)
                self.partition_selection_list.append(
                    [fs_key, is_restoring_partition, flat_image_part_description, dest_partition_key,
                     flattened_part_description,
                     dest_partition_key, flattened_part_description])
                num_destination_partitions += 1

        if num_destination_partitions == 0:
            # The destination disk must be empty.
            self.partition_selection_list.append(
                [self.dest_drive_node, is_restoring_partition, flat_image_part_description, self.dest_drive_node,
                 flattened_part_description,
                 dest_partition_key, flattened_part_description])

        # Populate combobox (right-hand side column)
        num_combo_box_entries = 0
        is_destination_partition_target_drive = False
        if 'partitions' in self.dest_drive_dict.keys() and len(self.dest_drive_dict['partitions'].keys()) > 0:
            # Loop over the partitions in in the destination drive
            for dest_partition_key in self.dest_drive_dict['partitions'].keys():
                if 'type' in self.dest_drive_dict['partitions'][dest_partition_key].keys() and self.dest_drive_dict['partitions'][dest_partition_key]['type'] == "extended":
                    # Do not add a destination combobox entry for any Extended Boot Record (EBR) destination partition
                    # nodes to reduce risk of user confusion.
                    continue
                if dest_partition_key == self.dest_drive_node:
                    is_destination_partition_target_drive = True
                flattened_part_description = dest_partition_key + ": " + CombinedDriveState.flatten_part(
                    self.dest_drive_dict['partitions'][dest_partition_key])
                self.destination_partition_combobox_list.append([dest_partition_key, flattened_part_description])
                num_combo_box_entries += 1

        # If there is no partitions on the destination disk, provide the option to remap the partitions to the whole
        # destination disk. If the source image doesn't have a partition table, also want to be able to remap partitons
        # to the destination disk. Finally, if the destination disk already has a filesystem directly on disk then
        # that would have already been handled above and there's no need to add a new entry to the combobox.
        if (num_combo_box_entries == 0 or not self.selected_image.has_partition_table()) and not is_destination_partition_target_drive:
            flattened_disk_description = self.dest_drive_node + ": " + CombinedDriveState.flatten_drive(self.dest_drive_dict)
            # If there are no partitions in the destination drive, we place the entire drive as the destination
            self.destination_partition_combobox_list.append([self.dest_drive_node, "WHOLE DRIVE " + flattened_disk_description])

        for mode in self.mode_list:
            self.destination_partition_combobox_cell_renderer_dict[mode].set_sensitive(True)

    def _swap_destination_partition_node_with_backup(self, liststore_iter):
        current_value = self.partition_selection_list.get_value(liststore_iter, 3)
        old_value = self.partition_selection_list.get_value(liststore_iter, 5)
        self.partition_selection_list.set_value(liststore_iter, 3, old_value)
        self.partition_selection_list.set_value(liststore_iter, 5, current_value)

        current_value = self.partition_selection_list.get_value(liststore_iter, 4)
        old_value = self.partition_selection_list.get_value(liststore_iter, 6)
        self.partition_selection_list.set_value(liststore_iter, 4, old_value)
        self.partition_selection_list.set_value(liststore_iter, 6, current_value)
