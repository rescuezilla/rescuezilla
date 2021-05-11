# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
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

from enum import Enum

MOUNT_DIR = "/mnt/backup"
IMAGE_EXPLORER_DIR = "/mnt/rescuezilla.image.explorer/"
RESCUEZILLA_MOUNT_TMP_DIR = "/mnt/rescuezilla.mount.tmp.folder/"
JOINED_FILES_NBD_DEVICE = "/dev/nbd0"
DECOMPRESSED_NBD_DEVICE = "/dev/nbd1"
MOUNTABLE_NBD_DEVICE = "/dev/nbd2"
# qemu-nbd device should be able to safely use the same nbd device as the joined/compressed/mountable above.
QEMU_NBD_NBD_DEVICE = "/dev/nbd4"

class Mode(Enum):
    BACKUP = 1
    RESTORE = 2
    VERIFY = 3
    CLONE = 4
    IMAGE_EXPLORER = 5

NETWORK_UI_WIDGET_MODES = [Mode.BACKUP, Mode.RESTORE, Mode.IMAGE_EXPLORER, Mode.VERIFY]

class Page(Enum):
    WELCOME = 1
    BACKUP_SOURCE_DRIVE_SELECTION = 2
    BACKUP_SOURCE_PARTITION_SELECTION = 3
    BACKUP_DESTINATION_LOCATION_SELECTION = 4
    BACKUP_DESTINATION_FOLDER = 5
    BACKUP_IMAGE_NAME_SELECTION = 6
    BACKUP_COMPRESSION_CUSTOMIZATION = 7
    BACKUP_CONFIRM_CONFIGURATION = 8
    BACKUP_PROGRESS = 9
    BACKUP_SUMMARY_SCREEN = 10
    RESTORE_SOURCE_LOCATION_SELECTION = 11
    RESTORE_SOURCE_IMAGE_SELECTION = 12
    RESTORE_DESTINATION_DRIVE_SELECTION = 13
    RESTORE_DESTINATION_PARTITION_SELECTION = 14
    RESTORE_CONFIRM_CONFIGURATION = 15
    RESTORE_PROGRESS = 16
    RESTORE_SUMMARY_SCREEN = 17
    VERIFY_SOURCE_LOCATION_SELECTION = 18
    VERIFY_SOURCE_IMAGE_SELECTION = 19
    VERIFY_PROGRESS = 20
    VERIFY_SUMMARY_SCREEN = 21
    CLONE_INTRODUCTION = 22
    CLONE_SOURCE_DRIVE_SELECTION = 23
    CLONE_DESTINATION_DRIVE_SELECTION = 24
    CLONE_PARTITIONS_TO_CLONE_SELECTION = 25
    CLONE_CONFIRM_CONFIGURATION = 26
    CLONE_PROGRESS = 27
    CLONE_SUMMARY_SCREEN = 28
    IMAGE_EXPLORER_SOURCE_LOCATION_SELECTION = 29
    IMAGE_EXPLORER_SOURCE_IMAGE_SELECTION = 30
    IMAGE_EXPLORER_PARTITION_MOUNT = 31

