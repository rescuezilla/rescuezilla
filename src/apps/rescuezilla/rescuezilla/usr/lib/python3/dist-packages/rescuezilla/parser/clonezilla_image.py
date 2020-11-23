# ----------------------------------------------------------------------
#   Copyright (C) 2003-2020 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2020 Rescuezilla.com <rescuezilla@gmail.com>
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
import pprint
import re
import subprocess
from datetime import datetime
from os.path import isfile, basename
from pathlib import Path

from babel.dates import format_datetime
from hurry.filesize import size, alternative

import utility
from parser.blkid import Blkid
from parser.ecryptfs import Ecryptfs
from parser.lvm import Lvm
from parser.parted import Parted
from parser.sfdisk import Sfdisk
from parser.swappt import Swappt
from utility import Utility, _


# Clonezilla images can be created by Clonezilla using its 'savedisk' and 'saveparts' functions. See the official
# Clonezilla documentation at [1] for some screenshots of this process.
#
# Clonezilla provides "Expert mode" with a number of configurable advanced parameters (see [2] for screenshots),
# including changing the compression mode from the standard gzip mode, and changing the imaging utility precedence
# from the standard filesystem-aware 'q2' (partclone > partimage > dd)" to another such as 'q1' (dd raw byte-for-byte
# copy)" mode or 'q' (ntfsclone > partimage > dd) mode. This imaging utility precedence information is not saved by
# Clonezilla, but it can easily be inferred by the filesystem image filename pattern. For example:
#   partclone:  "sdd2.ext4-ptcl-img.gz.aa"
#   ntfsclone:  "sdf12.ntfs-img.aa"
#   dd:         "sdf17.dd-img.aa"
#   PartImage:  "sdf10.aa"
#
# For space efficiency, Clonezilla does not backup the Linux swap space as a disk image, but as a text file with a
# name like "swappt-sda3.info" containing the swap partition's filesystem label and UUID information.
#
# Clonezilla's 'savedisk' mode allows MORE THAN ONE disk to be selected. The backup includes all the partitions and any
# partition tables from the selected disks. The image directory contains a file named 'disk' containing the space
# separated list of source disks (eg, "sdb nvme0n1"), and a file named 'parts' contains the space-separated file
# containing partitions in the backup, notably without separating the source disk from which it was created (eg,
# "sdb1 sdb2 sdb3 nvme0n1p1")
#
# Clonezilla's 'saveparts' mode allows more than one partition to be selected FROM MORE THAN ONE disk. Eg,
# it is valid to backup sda4, nvme0n1p4 and sdb3. The backup contains all selected partitions and all partition
# tables (if any). No file named 'disk' is created in this mode, but the 'parts' file continues to be a
# space-separated file exactly like the 'savedisk' case.
#
# Clonezilla provides all users (both in Beginner mode and Expert mode) if they would like to encrypt their backup
# with eCryptfs encryption. This can be identified by the presence of a file named "ecryptfs.info".
#
# Clonezilla supports "multipath" device nodes, such as HP Smart Array RAID device nodes (/dev/cciss/c0d0). this appears
# to be through an obsolete 'cciss' driver, so it's unclear the relevancy of this specific multipath device.
# FIXME: Understand multipath better.
#
# Clonezilla supports Logical Volume Manager (LVM). When an LVM drive is detected, the information is captured in
# several files. The LVM Volume Group (VG) to Physical Volume (PV) associations are captured in 'lvm_vg_dev.list',
# Logical Volume (LV) to Volume Group (VG) associations are captured in 'lvm_logv.list', and Logical Volume (LV)
# information is captured in lvm_[Logical Volume Name].conf. When an LVM logical volume contains a filesystem,
# the backup of the content of the filesystem uses the following pattern: "vgtest-lvtest.ntfs-ptcl-img.gz.aa". In
# other words, the multipath /dev/vgtest/lvtest device node is handled as a multipath Clonezilla device.
#
# [1] https://clonezilla.org/show-live-doc-content.php?topic=clonezilla-live/doc/01_Save_disk_image
# [2] https://clonezilla.org/clonezilla-live/doc/01_Save_disk_image/advanced/09-advanced-param.php
class ClonezillaImage:
    def __init__(self, absolute_clonezilla_img_path, enduser_filename):
        self.absolute_path = absolute_clonezilla_img_path
        self.enduser_filename = enduser_filename
        self.warning_dict = {}

        statbuf = os.stat(self.absolute_path)
        self.last_modified_timestamp = format_datetime(datetime.fromtimestamp(statbuf.st_mtime))
        print("Last modified timestamp " + self.last_modified_timestamp)

        self.image_format = "CLONEZILLA_FORMAT"
        dir = Path(absolute_clonezilla_img_path).parent.as_posix()
        print("Clonezilla directory : " + dir)

        self.short_device_node_partition_list = []
        self.short_device_node_disk_list = []
        self.lvm_vg_dev_dict = {}
        self.lvm_logical_volume_dict = {}
        self.dev_fs_dict = {}

        self.is_needs_decryption = False
        self.ecryptfs_info_dict = None
        ecryptfs_info_filepath = os.path.join(dir, "ecryptfs.info")
        if isfile(ecryptfs_info_filepath):
            try:
                # ecryptfs.info is plain text when the directory is encrypted and produces Input/Output error when decrypted
                Utility.read_file_into_string(ecryptfs_info_filepath)
                self.is_needs_decryption = True
            except:
                self.is_needs_decryption = False

        if self.is_needs_decryption:
            self.ecryptfs_info_dict = Ecryptfs.parse_ecryptfs_info(
                Utility.read_file_into_string(ecryptfs_info_filepath))
            self.short_device_node_disk_list = self.ecryptfs_info_dict['disk']
            self.short_device_node_partition_list = self.ecryptfs_info_dict['parts']
        else:
            # The 'parts' file contains space separated short partition device nodes (eg 'sda1 sda2 sda7') corresponding
            # to the partitions that were selected by the user during the original backup.
            parts_filepath = os.path.join(dir, "parts")
            if isfile(parts_filepath):
                self.short_device_node_partition_list = Utility.read_space_delimited_file_into_list(parts_filepath)
            else:
                # Every Clonezilla image encountered so far has a 'parts' file, so the backup is considered invalid
                # if none is present.
                raise FileNotFoundError("Unable to locate " + parts_filepath + " or file is encrypted")

            # The 'disk' file can contain *multiple* space-separated short device nodes (eg 'sda sdb'), but most
            # users will only backup one drive at a time using Clonezilla.
            #
            # Clonezilla images created using 'saveparts' function (rather than 'savedisk') does NOT have this file.
            disk_filepath = os.path.join(dir, "disk")
            if isfile(disk_filepath):
                self.short_device_node_disk_list = Utility.read_space_delimited_file_into_list(disk_filepath)
            else:
                print("Unable to locate " + disk_filepath)
                # Clonezilla images created using 'saveparts' (rather than 'savedisks') don't have this file. However, if
                # 'saveparts' is used on partitions that multiple disks that each contain partition tables then it's vital
                # that the short device nodes information is extracted in order for the user to be able to restoring their
                # intended partition table.
                #
                #
                parted_absolute_path_list = glob.glob(os.path.join(dir, "*-pt.parted"))
                for parted_absolute_path in parted_absolute_path_list:
                    self.short_device_node_disk_list.append(
                        re.sub('-pt.parted', '', os.path.basename(parted_absolute_path)))
                if len(self.short_device_node_disk_list) == 0:
                    # If the device list is still empty it must be due to using 'saveparts' on a drive without a
                    # partition table. Append these device odds onto the disk list for convenience.
                    self.short_device_node_disk_list += self.short_device_node_partition_list

            # TODO: Re-evaluate the need to parse this file, as far as I can tell all the information can be extracted
            # from the partition information.
            # The 'dev-fs.list' file contains the association between device nodes and the filesystems (eg '/dev/sda2 ext4')
            dev_fs_list_filepath = os.path.join(dir, "dev-fs.list")
            if isfile(dev_fs_list_filepath):
                self.dev_fs_dict = ClonezillaImage.parse_dev_fs_list_output(
                    Utility.read_file_into_string(dev_fs_list_filepath))
            else:
                # Not raising exception because older Clonezilla images don't have this file.
                print("Unable to locate " + dev_fs_list_filepath)

            # The 'blkid.list' file provides a snapshot of the partitions on the system at the time of backup. This data
            # is not particularly relevant during a restore operation, except potentially for eg, UUID.
            #
            # Danger: Do not mistake this structure for the current system's 'blkid' information.
            # TODO: Re-evaluate the need to parse this file. The risk of mistaken usage may outweigh its usefulness.
            self.blkid_dict = {}
            blkid_list_filepath = os.path.join(dir, "blkid.list")
            if isfile(blkid_list_filepath):
                self.blkid_dict = Blkid.parse_blkid_output(
                    Utility.read_file_into_string(os.path.join(dir, blkid_list_filepath)))
            else:
                # Not raising exception because older Clonezilla images don't have this file.
                print("Unable to locate " + blkid_list_filepath)

            # The 'lvm_vg_dev.list' file contains the association between an LVM VG (Logical Volume Manager volume group)
            # with a name eg 'vgtest', the LVM PV (physical volume) with a UUID name, and the device node that the physical
            # volume resides on eg, /dev/sdb.
            lvm_vg_dev_list_filepath = os.path.join(dir, "lvm_vg_dev.list")
            if isfile(lvm_vg_dev_list_filepath) and not self.is_needs_decryption:
                self.lvm_vg_dev_dict = Lvm.parse_volume_group_device_list_string(
                    Utility.read_file_into_string(lvm_vg_dev_list_filepath))
            else:
                print("No LVM volume group to device file detected in image")

            # The 'lvm_logv.list' file contains the association between device nodes and the filesystems (eg '/dev/sda2 ext4')
            lvm_logv_list_filepath = os.path.join(dir, "lvm_logv.list")
            if isfile(lvm_logv_list_filepath) and not self.is_needs_decryption:
                self.lvm_logical_volume_dict = Lvm.parse_logical_volume_device_list_string(
                    Utility.read_file_into_string(lvm_logv_list_filepath))
            else:
                print("No LVM logical volume file detected in image")

        self.parted_dict_dict = {}
        self.sfdisk_dict_dict = {}
        self.mbr_dict_dict = {}
        self.ebr_dict_dict = {}
        self.size_bytes = 0
        self.enduser_readable_size = "unknown"
        for short_disk_device_node in self.short_device_node_disk_list:
            self.size_bytes = 0
            # Clonezilla -pt.parted file lists size in sectors, rather than bytes (or end-user readable KB/MB/GB/TB as
            # Clonezilla's -pt.parted.compact file)
            parted_filepath = os.path.join(dir, short_disk_device_node + "-pt.parted")
            if isfile(parted_filepath) and not self.is_needs_decryption:
                self.parted_dict_dict[short_disk_device_node] = Parted.parse_parted_output(
                    Utility.read_file_into_string(parted_filepath))
                if 'capacity' in self.parted_dict_dict[short_disk_device_node] and 'logical_sector_size' in \
                        self.parted_dict_dict[short_disk_device_node]:
                    self.size_bytes = self.parted_dict_dict[short_disk_device_node]['capacity'] * \
                                      self.parted_dict_dict[short_disk_device_node]['logical_sector_size']
                else:
                    raise Exception("Unable to calculate disk capacity using " + parted_filepath + ": " + str(
                        self.parted_dict_dict[short_disk_device_node]))
            else:
                # Do not raise exception because parted partition table is not present when using 'saveparts'
                print("Unable to locate " + parted_filepath + " or file is encrypted")

            if self.ecryptfs_info_dict is not None and 'size' in self.ecryptfs_info_dict.keys():
                self.enduser_readable_size = self.ecryptfs_info_dict['size'].strip("_")
            else:
                # Covert size in bytes to KB/MB/GB/TB as relevant
                self.enduser_readable_size = size(int(self.size_bytes), system=alternative)
                sfdisk_filepath = os.path.join(dir, short_disk_device_node + "-pt.sf")
                if isfile(sfdisk_filepath) and not self.is_needs_decryption:
                    sfdisk_string = Utility.read_file_into_string(sfdisk_filepath)
                    self.sfdisk_dict_dict[short_disk_device_node] = {'absolute_path': sfdisk_filepath,
                                                                     'sfdisk_dict': Sfdisk.parse_sfdisk_dump_output(sfdisk_string),
                                                                     'sfdisk_file_length': len(sfdisk_string)
                                                                     }
                else:
                    # Do not raise exception because sfdisk partition table is often missing using Clonezilla image format,
                    # as `sfdisk --dump` fails for disks without a partition table.
                    print("Unable to locate " + sfdisk_filepath + " or file is encrypted")

            # There is a maximum of 1 MBR per drive (there can be many drives). Master Boot Record (EBR) is never
            # listed in 'parts' list.
            mbr_glob_list = glob.glob(os.path.join(dir, short_disk_device_node) + "*-mbr")
            for absolute_mbr_filepath in mbr_glob_list:
                short_mbr_device_node = basename(absolute_mbr_filepath).split("-mbr")[0]
                self.mbr_dict_dict[short_disk_device_node] = {'short_device_node': short_mbr_device_node,
                                                              'absolute_path': absolute_mbr_filepath}

            # There is a maximum of 1 EBR per drive (there can be many drives). Extended Boot Record (EBR) is never
            # listed in 'parts' list.
            ebr_glob_list = glob.glob(os.path.join(dir, short_disk_device_node) + "*-ebr")
            for absolute_ebr_filepath in ebr_glob_list:
                short_ebr_device_node = basename(absolute_ebr_filepath).split("-ebr")[0]
                self.ebr_dict_dict[short_disk_device_node] = {'short_device_node': short_ebr_device_node,
                                                              'absolute_path': absolute_ebr_filepath}

        self.image_format_dict_dict = collections.OrderedDict([])
        # Loops over the partitions listed in the 'parts' file
        for short_partition_device_node in self.short_device_node_partition_list:
            has_found_atleast_one_associated_image = False
            # For standard MBR and GPT partitions, the partition key listed in the 'parts' file has a directly
            # associated backup image, so check for this.
            image_format_dict = ClonezillaImage.scan_backup_image(dir, short_partition_device_node,
                                                                  self.is_needs_decryption)
            # If no match found check the LVM (Logical Volume Manager)
            if len(image_format_dict) == 0:
                # Loop over all the volume groups (if any)
                for vg_name in self.lvm_vg_dev_dict.keys():
                    # TODO: Evalulate if there are Linux multipath device nodes that hold LVM Physical Volumes.
                    # TODO: May need to adjust for multipath device node by replacing "/" with "-" for this node.
                    pv_short_device_node = re.sub('/dev/', '', self.lvm_vg_dev_dict[vg_name]['device_node'])
                    # Check if there is an associated LVM Physical Volume (PV) present
                    if short_partition_device_node == pv_short_device_node:
                        # Yes, the partition being analysed is associated with an LVM physical volume that contains
                        # an LVM Volume Group. Now determine all backup images associated to Logical Volumes that
                        # reside within this Volume Group.
                        for lv_path in self.lvm_logical_volume_dict.keys():
                            candidate_lv_path_prefix = "/dev/" + vg_name + "/"
                            # Eg, "/dev/cl/root".startswith("/dev/cl")
                            if lv_path.startswith(candidate_lv_path_prefix):
                                # Found a logical volume. Note: There may be more than one LV associated with an VG
                                # Set the scan prefix for the backup image to eg "cl-root"
                                logical_volume_scan_key = re.sub('/', '-', re.sub('/dev/', '', lv_path))
                                image_format_dict = ClonezillaImage.scan_backup_image(dir, logical_volume_scan_key,
                                                                                      self.is_needs_decryption)
                                if len(image_format_dict) != 0:
                                    image_format_dict['is_lvm_logical_volume'] = True
                                    image_format_dict['volume_group_name'] = vg_name
                                    image_format_dict['physical_volume_long_device_node'] = \
                                    self.lvm_vg_dev_dict[vg_name]['device_node']
                                    image_format_dict['logical_volume_long_device_node'] = lv_path
                                    self.image_format_dict_dict[logical_volume_scan_key] = image_format_dict
                                    has_found_atleast_one_associated_image = True
            else:
                has_found_atleast_one_associated_image = True
                self.image_format_dict_dict[short_partition_device_node] = image_format_dict

            if not has_found_atleast_one_associated_image:
                self.image_format_dict_dict[short_partition_device_node] = {'type': "missing",
                                                                            'prefix': short_partition_device_node,
                                                                            'is_lvm_logical_volume': False}
                # TODO: Improve conversion between /dev/ nodes to short dev node.
                long_partition_key = "/dev/" + short_partition_device_node
                if long_partition_key in self.dev_fs_dict.keys():
                    # Annotate have filesystem information from dev-fs.list file. This case is expected when during a
                    # backup Clonezilla or Rescuezilla failed to successfully image the filesystem, but may have
                    # succeeded for other filesystems.
                    fs = self.dev_fs_dict[long_partition_key]['filesystem']
                    self.image_format_dict_dict[short_partition_device_node]['filesystem'] = fs
                    # TODO: Consider removing warning_dict as image_format_dict is sufficient.
                    self.warning_dict[short_partition_device_node] = fs
                elif self.is_needs_decryption:
                    self.warning_dict[short_partition_device_node] = _("Needs decryption")
                else:
                    self.warning_dict[short_partition_device_node] = _("Unknown filesystem")

        # Unfortunately swap partitions are not listed in the 'parts' file. There does not appear to be any alternative
        # but scanning for the swap partitions and add them to the existing partitions, taking care to avoid duplicates
        # by rescanning what has already been scanned due to listing as an LVM logical volume.
        swap_partition_info_glob_list = glob.glob(os.path.join(dir, "swappt-*.info"))
        for swap_partition_info_glob in swap_partition_info_glob_list:
            key = Swappt.get_short_device_from_swappt_info_filename(swap_partition_info_glob)
            already_scanned = False
            for image_format_dict_key in self.image_format_dict_dict.keys():
                if key == self.image_format_dict_dict[image_format_dict_key]["prefix"]:
                    already_scanned = True
                    break
            if not already_scanned and not self.is_needs_decryption:
                self.image_format_dict_dict[key] = Swappt.parse_swappt_info(
                    Utility.read_file_into_string(swap_partition_info_glob))
                self.image_format_dict_dict[key]['type'] = "swap"
                self.image_format_dict_dict[key]['prefix'] = key
                self.image_format_dict_dict[key]['is_lvm_logical_volume'] = False
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.image_format_dict_dict)

    @staticmethod
    def _get_glob_list_of_split_images(path_with_wildcard):
        glob_list = []
        for f in glob.glob(path_with_wildcard):
            # Collect the files ending in eg, ".aa", ".ab" etc
            # It's vital that this is in alphabetical order.
            # FIXME: Potentially this could collect files ending in ".log"
            if re.search(r'[.][a-zA-Z]+$', f):
                glob_list.append(f)
        # It's not guaranteed the wildcard returns in alphabetical order, so we sort it (alphabetically, not lexically).
        glob_list.sort()
        return glob_list

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
        return ClonezillaImage.extract_image_compression_from_file_utility(str(stdout))

    @staticmethod
    def scan_backup_image(dir, prefix, is_needs_decryption):
        image_format_dict = {}
        dd_image_abs_path_glob_list = ClonezillaImage._get_glob_list_of_split_images(
            os.path.join(dir, prefix + "[.]dd-img[.][a-zA-Z][a-zA-Z]"))
        ntfsclone_image_abs_path_glob_list = ClonezillaImage._get_glob_list_of_split_images(
            os.path.join(dir, prefix + "[.]ntfs-img[.][a-zA-Z][a-zA-Z]"))
        partclone_image_abs_path_glob_list = ClonezillaImage._get_glob_list_of_split_images(
            os.path.join(dir, prefix + "[.]*-ptcl-img[.][a-zA-Z]*[.][a-zA-Z][a-zA-Z]"))
        partimage_image_abs_path_glob_list = ClonezillaImage._get_glob_list_of_split_images(
            os.path.join(dir, prefix + "[.][a-zA-Z][a-zA-Z]"))
        swap_partition_info_glob_list = glob.glob(os.path.join(dir, "swappt-" + prefix + ".info"))

        if len(dd_image_abs_path_glob_list) > 0:
            image_format_dict = {'type': "dd",
                                 'absolute_filename_glob_list': dd_image_abs_path_glob_list,
                                 'compression': ClonezillaImage.detect_compression(dd_image_abs_path_glob_list),
                                 'binary': "partclone.dd",
                                 "prefix": prefix,
                                 'is_lvm_logical_volume': False}

        elif len(ntfsclone_image_abs_path_glob_list) > 0:
            image_format_dict = {'type': "ntfsclone",
                                 'absolute_filename_glob_list': ntfsclone_image_abs_path_glob_list,
                                 'compression': ClonezillaImage.detect_compression(ntfsclone_image_abs_path_glob_list),
                                 'binary': "ntfsclone",
                                 "prefix": prefix,
                                 'is_lvm_logical_volume': False}
        elif len(partclone_image_abs_path_glob_list) > 0:
            m = utility.REMatcher(os.path.basename(partclone_image_abs_path_glob_list[0]))
            # sdf1.btrfs-ptcl-img.gz.aa
            if m.match(r"" + prefix + "[.]([a-zA-Z0-9+]+)-ptcl-img[.][a-zA-Z0-9]+[.]aa"):
                # Clonezilla's image has to be detected. The filename only contains the compression for partclone images, but not
                # for the other formats.
                filesystem = m.group(1)
                image_format_dict = {'type': "partclone",
                                     'absolute_filename_glob_list': partclone_image_abs_path_glob_list,
                                     'compression': ClonezillaImage.detect_compression(
                                         partclone_image_abs_path_glob_list),
                                     'filesystem': filesystem,
                                     'binary': "partclone." + filesystem,
                                     "prefix": prefix,
                                     'is_lvm_logical_volume': False}
        # PartImage images have a much wider wildcard that will match the above formats, so it's important we test it last
        elif len(partimage_image_abs_path_glob_list) > 0:
            image_format_dict = {'type': "partimage",
                                 'absolute_filename_glob_list': partimage_image_abs_path_glob_list,
                                 'compression': ClonezillaImage.detect_compression(partimage_image_abs_path_glob_list),
                                 'binary': 'partimage',
                                 "prefix": prefix,
                                 'is_lvm_logical_volume': False}
        elif len(swap_partition_info_glob_list) > 0:
            if not is_needs_decryption:
                image_format_dict = Swappt.parse_swappt_info(
                    Utility.read_file_into_string(swap_partition_info_glob_list[0]))
                image_format_dict['type'] = "swap"
                image_format_dict['prefix'] = prefix
                image_format_dict['is_lvm_logical_volume'] = False
        else:
            print("Unable to find associated image for " + prefix)
        return image_format_dict

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
            raise Exception("Unable to detect file compression: " + output_of_file_utility_string)

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

    @staticmethod
    def parse_dev_fs_list_output(dev_fs_list_string):
        dev_fs_dict = collections.OrderedDict([])
        for line in dev_fs_list_string.splitlines():
            # Ignore comment lines (lines starting with hash symbol)
            if not re.match(r'^#', line):
                split_line = line.split(" ")
                if len(split_line) > 0:
                    long_dev_node = split_line[0]
                    if len(split_line) > 1:
                        dev_fs_dict[long_dev_node] = {"filesystem": split_line[1]}
                    if len(split_line) > 2:
                        dev_fs_dict[long_dev_node]['size'] = split_line[2]
        return dev_fs_dict

    def get_enduser_friendly_partition_description(self):
        flat_string = ""
        drive_index = 0
        for short_disk_key in self.short_device_node_disk_list:
            if self.ecryptfs_info_dict is not None and 'size' in self.ecryptfs_info_dict.keys():
                flat_string += "ECRYPTFS: "
            if len(self.short_device_node_disk_list) > 1:
                if drive_index == 0:
                    # Capitalized text that (in conjunction with a error box) will help assist Rescuezilla users in
                    # understanding Clonezilla multidisk images are not yet fully supported.
                    flat_string += "MULTIDISK "
                flat_string += _("Drive {drive_number}".format(drive_number=str(drive_index + 1))) + ": "
            for image_format_dict_key in self.image_format_dict_dict.keys():
                if self.does_image_key_belong_to_device(image_format_dict_key, short_disk_key):
                    if self.image_format_dict_dict[image_format_dict_key]['is_lvm_logical_volume']:
                        flat_string += "(" + image_format_dict_key + ": " + self.flatten_partition_string(
                            short_disk_key,
                            image_format_dict_key) + ") "
                    else:
                        base_device_node, partition_number = Utility.split_device_string(image_format_dict_key)
                        flat_string += "(" + str(partition_number) + ": " + self.flatten_partition_string(
                            short_disk_key,
                            image_format_dict_key) + ") "
            drive_index += 1
        return flat_string

    def flatten_partition_string(self, short_disk_key, partition_short_device_node):
        flat_string = ""

        if 'filesystem' in self.image_format_dict_dict[partition_short_device_node].keys():
            flat_string += self.image_format_dict_dict[partition_short_device_node]['filesystem']
        elif 'type' in self.image_format_dict_dict[partition_short_device_node].keys():
            if self.image_format_dict_dict[partition_short_device_node]['type'] == "ntfsclone":
                flat_string += "ntfsclone"
            elif self.image_format_dict_dict[partition_short_device_node]['type'] == "partimage":
                flat_string += "partimage"
            elif self.image_format_dict_dict[partition_short_device_node]['type'] == "dd":
                flat_string += "dd-img"
            elif self.image_format_dict_dict[partition_short_device_node]['type'] == "swap":
                flat_string += "swap"
        else:
            # TODO: Improve conversion between /dev/ nodes to short dev node.
            long_partition_key = "/dev/" + re.sub("-", "/", partition_short_device_node)
            if long_partition_key in self.dev_fs_dict.keys():
                # TODO: Consider raising exception?
                flat_string += "NOT FOUND: " + self.dev_fs_dict[long_partition_key]['filesystem']
            else:
                flat_string += "NOT FOUND: " + long_partition_key

        if 'is_lvm_logical_volume' in self.image_format_dict_dict[partition_short_device_node].keys() and \
                self.image_format_dict_dict[partition_short_device_node]['is_lvm_logical_volume']:
            return flat_string

        image_base_device_node, image_partition_number = Utility.split_device_string(partition_short_device_node)
        if short_disk_key in self.parted_dict_dict.keys() and image_partition_number in \
                self.parted_dict_dict[short_disk_key]['partitions'].keys():
            size_in_bytes = self.parted_dict_dict[short_disk_key]['partitions'][image_partition_number]['size'] * \
                            self.parted_dict_dict[short_disk_key]['logical_sector_size']
            flat_string += " " + str(size(int(size_in_bytes), system=alternative))

        return flat_string

    # Multidisk helper
    def does_image_key_belong_to_device(self, image_format_dict_key, short_device_key):
        if self.image_format_dict_dict[image_format_dict_key]['is_lvm_logical_volume'] and \
                self.image_format_dict_dict[image_format_dict_key]['physical_volume_long_device_node'].startswith(
                        "/dev/" + short_device_key):
            return True
        elif image_format_dict_key.startswith(short_device_key):
            return True
        else:
            return False

    def has_partition_table(self):
        # TODO: Handle multidisk Clonezilla images
        short_selected_image_drive_node = self.short_device_node_disk_list[0]
        # Using MBR over sfdisk, as sometimes Clonezilla sfdisk file is empty but a valid MBR file still present.
        if short_selected_image_drive_node not in self.mbr_dict_dict.keys():
            return False
        else:
            return len(self.mbr_dict_dict[short_selected_image_drive_node]) != 0
