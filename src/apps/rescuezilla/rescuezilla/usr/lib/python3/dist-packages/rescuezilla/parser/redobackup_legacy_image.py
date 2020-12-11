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

import collections
import glob
import os
import re
import subprocess
import time

from parser.partclone import Partclone
from parser.sfdisk import Sfdisk
from utility import Utility, _


# Background: Redo Backup and Recovery has a complicated version history: it was originally actively developed
# between 2010-2012 before being abandoned by the original author, with some intrepid users of Redo Backup
# Sourceforge forum creating several forks [1]. Each of the forks have their own quirks and bugs.
#
# To unify all the Redo Backup and Recovery forks under the Rescuezilla banner, and provide the best end-user
# experience, all Redo Backup and Recovery formats are supported as far as practical.
#
# Redo Backup and Recovery only supported /dev/sdX device nodes, and Rescuezilla 1.5 images supported /dev/sdX and
# /dev/nvmeAnBp3 nodes
#
# [1] https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#identifying-redo-backup-versions
class RedoBackupLegacyImage:
    def __init__(self, absolute_path, enduser_filename, filename):
        # Redo Backup images never need decryption
        self.is_needs_decryption = False
        # Path to ".backup" file
        self.absolute_path = absolute_path
        self.enduser_filename = enduser_filename
        self.proc = collections.OrderedDict()
        env = Utility.get_env_C_locale()
        print("Reading backup : " + absolute_path)
        dirname = os.path.dirname(absolute_path)
        self.warning_dict = {}

        if filename.endswith(".backup"):
            prefix = filename.split(".backup")[0]
            print("prefix: " + prefix)
        else:
            raise ValueError("Expected Rescuezilla backup to end with .backup: " + absolute_path)

        rescuezilla_version_abs_path = os.path.join(dirname, prefix + ".rescuezilla.backup_version")
        if not os.path.exists(rescuezilla_version_abs_path):
            self.image_format = "REDOBACKUP_0.9.8_1.0.4_FORMAT"
        else:
            self.image_format = "RESCUEZILLA_1.5_FORMAT"
            self.rescuezilla_version = Utility.read_file_into_string(rescuezilla_version_abs_path).strip()
            print("Backup originally created with Rescuezilla version: " + self.rescuezilla_version)

        self.last_modified_timestamp = str(time.ctime(os.stat(absolute_path).st_mtime))
        print("Last modified timestamp " + self.last_modified_timestamp)

        self.short_device_node_partition_list = Utility.read_linebreak_delimited_file_into_list(absolute_path)
        print("Source_partitions: " + str(self.short_device_node_partition_list))

        self.backup_version = Utility.read_file_into_string(absolute_path).strip()
        print("Backup version: " + str(self.backup_version))

        self.size_bytes = int(Utility.read_file_into_string(os.path.join(dirname, prefix + ".size").strip()))
        print("Size: " + str(self.size_bytes))
        # Covert size in bytes to KB/MB/GB/TB as relevant
        self.enduser_readable_size = Utility.human_readable_filesize(int(self.size_bytes))

        self.mbr_absolute_path = os.path.join(dirname, prefix + ".mbr")
        # Get the size of the MBR image because a Sourceforge user named chcatzsf released two unofficial
        # German-language Redo Backup and Recovery update based on Ubuntu 13.10 and Ubuntu 14.04. These two versions
        # incorrectly created 512 byte Master Boot Record backup images. More information [1].
        #
        # [1] https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in-chcatzsfs-ubuntu-1310-and-1404-releases-german-language-only
        self.mbr_size = int(os.stat(self.mbr_absolute_path).st_size)
        if self.mbr_size == 512:
            # Explain the situation to users with this issue and link to further information about how the GRUB boot
            # loader can be regenerated, and confirm whether they wish to proceed.
            truncated_bootloader_bug_url = "https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in-chcatzsfs-ubuntu-1310-and-1404-releases-german-language-only";
            # Context for translators: Two popular unofficial Redo Backup v1.0.4 updates by Sourceforge user chcatzsf
            # have major bugs where bootloaders like GRUB are not not fully backed up, so Linux-based operating
            # cannot boot after a restore. This bug only affected those two updates (German-language only) and the
            # problem can be fixed with careful manual intervention. Translating this message into languages other
            # than English and German is not required. Full details in:
            # https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in
            # -chcatzsfs-ubuntu-1310-and-1404-releases-german-language-only
            self.warning_dict[enduser_filename] = _("The backup's bootloader data is shorter than expected. This happens with backups created by an unofficial Redo Backup update. If the backup contained certain bootloaders like GRUB, the restored hard drive will not boot correctly without a manual fix. All data is still fully recoverable but manual intervention may required to restore the bootloader. Please consult {url} for information and assistance. The destination drive has not yet been modified. Do you wish to continue with the restore?").format(url=truncated_bootloader_bug_url)

        self.sfdisk_absolute_path = os.path.join(dirname, prefix + ".sfdisk")
        sfdisk_string = Utility.read_file_into_string(self.sfdisk_absolute_path).strip()
        print("sfdisk: " + str(sfdisk_string))
        self.sfdisk_dict = {}
        # Louvetch's English and French Redo Backup and Recovery update based on Ubuntu 16.04 (Xenial) creates empty
        # sfdisk partition table file for both MBR and GPT disks. More information [1]
        # [1] https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in-louvetchs-ubuntu-1604-releases
        if sfdisk_string == "":
            empty_sfdisk_bug_url = "https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#bugs-in-louvetchs-ubuntu-1604-releases"
            # Context for translators: The two popular unofficial updates of Redo Backup v1.0.4 by Sourceforge user louvetch have a major bug.
            # This major bug affected both the English language and French language versions of this unofficial update. All data can be restored with careful
            # manual intervention. Given the popularity of those unofficial updates, translating this error message is still important.
            self.warning_dict[enduser_filename] = _("The backup's extended partition information is empty or missing. This happens with incomplete backups created by an unofficial Redo Backup update. If the backup contains extended partitions, these will not restore correctly. All data is still fully recoverable but manual intervention is required to fully restore the extended partitions. Please consult {url} for information and assistance. The destination drive has not yet been modified. Do you wish to continue with the restore?").format(url=empty_sfdisk_bug_url)
        else:
            self.sfdisk_dict = Sfdisk.parse_sfdisk_dump_output(sfdisk_string)

        # Cannot rely on sfdisk drive name due to some Redo Backup versions not populating this file correctly.
        if 'device' in self.sfdisk_dict.keys():
            self.short_device_node_disk_list = [self.sfdisk_dict['device']]
        else:
            self.short_device_node_disk_list = ["unknown"]

        # The NVMe drive handling on Rescuezilla v1.0.5.1+ set the drive name in the .backup file start with "sdz" to
        # preserve the ability to restore with older versions of Rescuezilla (which read the source drive). Since v2.0,
        # this string is used as a key into sfdisk partitions, so the ".backup" partition list such containing elements
        # like "sdz3" needs to be renamed to eg, "nvme0n1p3" here to preserve full backwards compatibility.
        if 'partitions' in self.sfdisk_dict.keys() and len(self.sfdisk_dict['partitions'].keys()) > 1:
            # Long drive node extracted from sfdisk dictionary
            sfdisk_long_drive_node = list(self.sfdisk_dict['partitions'].keys())[0]
            actual_base_device_node, first_partition_number = Utility.split_device_string(sfdisk_long_drive_node)
            for i in range(len(self.short_device_node_partition_list)):
                node_to_potentially_rename = self.short_device_node_partition_list[i]
                if node_to_potentially_rename.startswith("sdz") and actual_base_device_node != "sdz":
                    # This node is renamed, and the list is updated.
                    fake_base_device_node, actual_partition_number = Utility.split_device_string(node_to_potentially_rename)
                    corrected_long_device_node = Utility.join_device_string(actual_base_device_node, actual_partition_number)
                    corrected_short_device_node = re.sub('/dev/', '', corrected_long_device_node)
                    self.short_device_node_partition_list[i] = corrected_short_device_node

        self.partition_restore_command_dict = collections.OrderedDict()
        self.partclone_info_dict = collections.OrderedDict([])
        for short_device_node in self.short_device_node_partition_list:
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            image_match_string = os.path.join(dirname, prefix + "_part" + str(partition_number) + ".*")
            # Get absolute path partition images. Eg, [/path/to/20200813_part3.000, /path/to/20200813_part3.001 etc]
            abs_partclone_image_list = glob.glob(image_match_string)
            # Sort by alphabetical sort. Lexical sort not required here because fixed number of digits (so no risk
            # of "1, 10, 2, 3" issues)
            abs_partclone_image_list.sort()
            if len(abs_partclone_image_list) == 0:
                # The legacy Redo Backup and Recovery format cannot distinguish between failed partclone backup and a
                # user who chose not to backup a partition
                self.warning_dict[short_device_node] = _("Cannot find partition's associated partclone image")
                continue
            self.partition_restore_command_dict[partition_number] = {'abs_image_glob': abs_partclone_image_list}

            command = "partclone"
            # Rescuezilla v1.0.5 format creates partition to filesystem mapping files
            command_filepath = os.path.join(dirname, prefix + ".partclone.command.part" + str(partition_number))
            if os.path.isfile(command_filepath):
                command = Utility.read_file_into_string(command_filepath).strip()
                print(str(short_device_node) + ": " + command)
                self.partition_restore_command_dict[partition_number]['restore_binary'] = command

            # Get partclone.info
            cat_cmd_list = ["cat"] + abs_partclone_image_list
            pigz_cmd_list = ["pigz", "--decompress", "--stdout"]
            partclone_info_cmd_list = ["partclone.info", "--source", "-"]
            Utility.print_cli_friendly("partclone ", [cat_cmd_list, pigz_cmd_list, partclone_info_cmd_list])
            self.proc['cat_partclone' + short_device_node] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE, env=env,
                                                                      encoding='utf-8')
            self.proc['pigz' + short_device_node] = subprocess.Popen(pigz_cmd_list,
                                                             stdin=self.proc['cat_partclone' + short_device_node].stdout,
                                                             stdout=subprocess.PIPE, env=env, encoding='utf-8')
            self.proc['partclone_info' + short_device_node] = subprocess.Popen(partclone_info_cmd_list,
                                                                           stdin=self.proc['pigz' + short_device_node].stdout,
                                                                           stdout=subprocess.PIPE,
                                                                           stderr=subprocess.PIPE, env=env,
                                                                           encoding='utf-8')
            self.proc['cat_partclone' + short_device_node].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
            self.proc['pigz' + short_device_node].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
            output, err = self.proc['partclone_info' + short_device_node].communicate()
            print("partclone_info: Exit output " + str(output) + "stderr " + str(err))
            self.partclone_info_dict[partition_number] = Partclone.parse_partclone_info_output(err)
            if len(self.partclone_info_dict[partition_number]) == 0:
                # If unable to read the partclone.info output, treat this as a dd image (see unit test for
                # partclone.info example output for this case).
                print(self.absolute_path + ": Could not read partclone info dict for " + short_device_node + ". Treating it as a dd image.")
                self.partclone_info_dict[partition_number] = {'filesystem': "dd"}

    def has_partition_table(self):
        # All Redo Backup legacy images have at least the MBR file, even if the sfdisk file is empty or the MBR itself
        # is truncated to 512 bytes.
        return True

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        index = 0
        for short_device_node in self.short_device_node_partition_list:
            base_device_node, partition_number = Utility.split_device_string(short_device_node)
            flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(short_device_node) + ") "
            index += 1
        return flat_string

    def flatten_partition_string(self, short_device_node):
        flat_string = ""
        base_device_node, partition_number = Utility.split_device_string(short_device_node)
        if partition_number in self.partition_restore_command_dict.keys() and 'command' in self.partition_restore_command_dict[partition_number].keys():
            # On the Rescuezilla v1.0.5 image format, the partition restore command is easily accessible.
            command = self.partition_restore_command_dict[partition_number]['command']
            filesystem = re.sub('partclone.', '', command)
            flat_string += filesystem + " "
        elif partition_number in self.partclone_info_dict.keys() and 'filesystem' in self.partclone_info_dict[partition_number].keys():
            # Otherwise, the value detected by partclone.info must be used (which is known to be unreliable).
            flat_string += self.partclone_info_dict[partition_number]['filesystem'] + " "
        else:
            print(self.absolute_path + ": Unable to use " + str(partition_number) + " from " + short_device_node + " in " + str(self.partclone_info_dict) + " or " + str(self.partclone_info_dict))
            flat_string = "NOT_FOUND "

        # Convert short device node to long device node by prepending "/dev/" (this simply approach is only correct for
        # Rescuezilla 1.0.5 and Redo Backup and Recovery images, as the format never supported multipath device nodes.
        long_device_node = "/dev/" + short_device_node
        if 'partitions' in self.sfdisk_dict.keys() and long_device_node in self.sfdisk_dict['partitions'].keys():
            # Get the partition size from sfdisk partition table
            flat_string += Utility.human_readable_filesize(int(self.sfdisk_dict['partitions'][long_device_node]['size']) * 512)
        elif partition_number in self.partclone_info_dict.keys() and 'size' in self.partclone_info_dict[partition_number].keys():
            # Otherwise, use the filesystem size from partclone.info
            flat_string += Utility.human_readable_filesize(int(self.partclone_info_dict[partition_number]['size']['bytes']))
        else:
            print(self.absolute_path + ": Unable to use " + str(partition_number) + " from " + short_device_node + " in " + str(self.sfdisk_dict) + " or " + str(self.partclone_info_dict))
            flat_string = "NOT_FOUND "
        return flat_string
