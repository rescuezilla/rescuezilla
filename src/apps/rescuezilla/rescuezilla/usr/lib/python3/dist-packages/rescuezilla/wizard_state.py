# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
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

from enum import Enum

MOUNT_DIR = "/mnt/backup"

class Mode(Enum):
    BACKUP = 1
    RESTORE = 2


class Page(Enum):
    WELCOME = 1
    BACKUP_SOURCE_DRIVE_SELECTION = 2
    BACKUP_SOURCE_PARTITION_SELECTION = 3
    BACKUP_DESTINATION_LOCATION_SELECTION = 4
    BACKUP_DESTINATION_FOLDER = 5
    BACKUP_IMAGE_NAME_SELECTION = 6
    BACKUP_CONFIRM_CONFIGURATION = 7
    BACKUP_PROGRESS = 8
    BACKUP_SUMMARY_SCREEN = 9
    RESTORE_SOURCE_LOCATION_SELECTION = 10
    RESTORE_SOURCE_IMAGE_SELECTION = 11
    RESTORE_DESTINATION_DRIVE_SELECTION = 12
    RESTORE_DESTINATION_PARTITION_SELECTION = 13
    RESTORE_CONFIRM_CONFIGURATION = 14
    RESTORE_PROGRESS = 15
    RESTORE_SUMMARY_SCREEN = 16
