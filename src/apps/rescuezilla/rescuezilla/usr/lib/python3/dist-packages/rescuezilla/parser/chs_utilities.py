# ----------------------------------------------------------------------
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
import glob
import math
import os
import re
import shutil
from parser.parted import Parted
from parser.sfdisk import Sfdisk
from utility import Utility, _
from logger import Logger

# Port of Clonezilla's handling of drive addressing.
#
# For a great 5 minute introduction to CHS addressing, watch Nostalgia Nerd's YouTube video [1]. Cylinder-head-sector
# addressing is largely obsolete after having been replaced by LBA (logical block addressing) in the mid-1990s.
# However by many accounts NTFS filesytems need their own CHS metadata updated when an NTFS filesystem is moved
# between physical hard drives of different geometries. Updating the NTFS CHS information is required not only on
# older drives and operating systems (such as an IDE drive running Windows Server 2003) but also modern drives and
# operating systems (such as NVMe drives with Windows 10).
#
# To update the CHS information on an NTFS filesystem the partclone package comes with a tool named
# partclone.ntfsfixboot (which has a partclone.ntfsreloc symlink). Its man page claims it "deals with braindeadness
# with moving NTFS filesystems". This tool allows updating the CHS information within the NTFS filesystem. Note:
# partclone.ntfsreloc/partclone.ntfsfixboot tool should not be confused with the "ntfsfix" tool.
#
# The original Clonezilla code that is ported to Python below often referenced a 3 page Sourceforge discussion [2] from
# 2009. A key point of that discussion is sfdisk apparently may produce the wrong drive geometry, while a BIOS
# feature named EDD ( Enhanced Disk Device) exposes the correct numbers. Here's an explanation of the EDD feature [
# 3]: "x86 systems suffer from a disconnect between what BIOS believes is the boot disk, and what Linux thinks BIOS
# thinks is the boot disk.  BIOS Enhanced Disk Device Services (EDD) 3.0 provides the ability for disk adapter BIOSs
# to tell the OS what it believes is the boot disk." Note: EDD requires a boot flag for the /sys/firmware/edd folder to
# be exposed, but not all kernels are compiled with flag so the boot flag may not have any effect on some kernels.
# As of 2021, even new versions of Clonezilla continue to expose /sys/firmware/edd folder, but only some Rescuezilla
# ISO images seem to be able to use edd=on correctly.
#
# [1] https://www.youtube.com/watch?v=gd5vKobmZ3Q
# [2] https://sourceforge.net/p/clonezilla/discussion/Help/thread/05a581f3/
# [3] http://lwn.net/Articles/9042/
class ChsUtilities:
    # Relocate NTFS filesystem CHS (cylinder-head-sector) information using partclone.ntfsfixboot. Read the comment
    # block of this ChsUtilities class for detailed explanation why this is required.
    #
    # This function is a port of some of Clonezilla's run_ntfsreloc_part function from sbin/ocs-functions file.
    @staticmethod
    def adjust_ntfs_filesystem_chs_geometry_information(ntfs_partition_long_device_node, ntfs_partition_start_sector,
                                                        destination_disk_geometry_dict, is_edd_geometry, logger):
        cylinders = str(destination_disk_geometry_dict['cylinders'])
        ntfsfixboot_geometry_options = []
        if destination_disk_geometry_dict is not None:
            ntfsfixboot_geometry_options = [
                # "-h, Specify number of heads per track. If omitted, determined via ioctl."
                "-h", str(destination_disk_geometry_dict['heads']),
                # "-t, Specify number of sectors per track. If omitted, determined via ioctl."
                "-t", str(destination_disk_geometry_dict['sectors'])
            ]
        if ntfs_partition_start_sector is not None:
            # "-s, New start sector to write. If omitted, determined via ioctl."
            ntfsfixboot_geometry_options += ['-s', str(ntfs_partition_start_sector)]

        ntfsfixboot_dry_run_cmd_list = ["partclone.ntfsfixboot"] + ntfsfixboot_geometry_options + [ntfs_partition_long_device_node]
        process, flat_command_string, failed_message = Utility.run("Dry-run adjust filesystem geometry for the NTFS partition",
                                                                   ntfsfixboot_dry_run_cmd_list, use_c_locale=True,
                                                                   logger=logger)
        if process.returncode == 1:
            return True, _("No changes needed for NTFS filesystem geometry of {ntfs_device}").format(ntfs_device=ntfs_partition_long_device_node)

        # Regardless of if a change is needed, try to write
        # "-w, Write new start sector to the partition."
        ntfsfixboot_cmd_list = ["partclone.ntfsfixboot"] + ['-w'] + ntfsfixboot_geometry_options + [ntfs_partition_long_device_node]
        process, flat_command_string, failed_message = Utility.run("Adjust filesystem geometry for the NTFS partition",
                                                                   ntfsfixboot_cmd_list, use_c_locale=False,
                                                                   logger=logger)
        if process.returncode != 0:
            return False, failed_message

        # It's unclear why there are difference between EDD and sfdisk geometry, so let the user know the source.
        if is_edd_geometry:
            geometry_source = "EDD"
        else:
            geometry_source = "sfdisk"
        return True, _("Successfully adjusted NTFS filesystem geometry of {ntfs_device} using values from {geometry_source}").format(ntfs_device=ntfs_partition_long_device_node, geometry_source=geometry_source)

    # Get target drive's CHS geometry by querying the EDD and sfdisk with the same order of operations that Clonezilla
    # uses. This function is extracted from Clonezilla's run_ntfsreloc_part function.
    @staticmethod
    def query_drive_chs_geometry(long_device_node, image_sfdisk_geometry_dict, logger):
        edd_geometry_dict = None
        sfdisk_geometry_dict = None
        is_edd_geometry = False
        return_message = ""
        # First try getting the geometry from the EDD
        is_success, value = ChsUtilities._get_chs_geometry_from_edd(long_device_node, logger)
        if is_success:
            edd_geometry_dict = value
            print("edd geometry dict " + long_device_node + ": " + str(edd_geometry_dict))
        else:
            # Save return message
            return_message = value

        # Clonezilla's -e (--load-geometry) option is not set by default. The option sets the
        # load_HD_CHS_from_img variable that requests to load the CHS geometry from the -chs.sf file within the
        # image. This data is generally not relevant for the destination drive, which may have different geometry
        # from the original drive. TODO: Consider implementing this option (using image_sfdisk_geometry_dict)

        # When load_HD_CHS_from_img is not set then Clonezilla queries the destination drive's geometry using sfdisk

        # The --show-geometry call takes just a fraction of a second to run, so unlike Clonezilla always run it, because
        # that places both values in the log file which may be useful for debugging.
        process, flat_command_string, failed_message = Utility.run("Retreiving disk geometry with sfdisk",
                                                                   ["sfdisk", "--show-geometry", long_device_node],
                                                                   use_c_locale=True, logger=logger)
        if process.returncode == 0:
            sfdisk_geometry_dict = Sfdisk.parse_sfdisk_show_geometry(process.stdout)
            print("sfdisk geometry dict " + long_device_node + ": " + str(sfdisk_geometry_dict))
        else:
            return_message += failed_message

        geometry_dict = None
        if edd_geometry_dict is not None and len(edd_geometry_dict) != 0:
            is_edd_geometry = True
            geometry_dict = edd_geometry_dict
        elif sfdisk_geometry_dict is not None and len(sfdisk_geometry_dict) != 0:
            is_edd_geometry = False
            geometry_dict = sfdisk_geometry_dict

        return geometry_dict, is_edd_geometry, return_message

    # Query the CHS (Cylinder-head-sector) drive geometry from the EDD (Enhanced Disk Device).
    #
    # Implementation of Clonezilla's get_RawCHS_of_HD_from_EDD function from sbin/ocs-functions file
    #
    # Clonezilla gets the EDD device path by first using device name with the edd_id utility, then using the MBR
    # signature, then using the disk capacity. Rescuezilla takes an identical approach to maximum Clonezilla
    # compatibility.
    #
    # TODO: Revisit this, because there's likely a better way to do this than how Clonezilla does it.
    @staticmethod
    def _get_chs_geometry_from_edd(long_device_node, logger):
        if not os.path.isdir("/sys/firmware/edd"):
            process, flat_command_string, failed_message = Utility.run(
                "Loading EDD (Enhanced Disk Device) kernel module",
                ["modprobe", "edd"],
                use_c_locale=True, logger=logger)
            # Clonezilla ignores return code, so same here.
        if not os.path.isdir("/sys/firmware/edd"):
            return False, "Kernel EDD (sysfs interface to BIOS EDD (Enhanced Disk Device) information) not supported!\nYou can try to enable it if it's builtin by putting edd=on as boot parameter."

        # Determine the /sys/firmware/edd path
        edd_device_mapping = ""
        # FIXME: It's unclear if the /lib/udev/edd_id executable is still relevant on modern Linux systems. It does not
        # FIXME: appear available anywhere.
        if shutil.which("/lib/udev/edd_id") is not None:
            process, flat_command_string, failed_message = Utility.run("Get edd device mapping)",
                                                                       ["/lib/udev/edd_id", long_device_node],
                                                                       use_c_locale=False, logger=logger)
            if process.returncode != 0:
                print(failed_message)
            else:
                edd_device_mapping = process.stdout
        else:
            print("Could not find /lib/udev/edd_id")

        if edd_device_mapping == "":
            is_success, value = ChsUtilities._find_edd_sysfs_path_using_mbr_disk_signature(long_device_node, logger)
            if not is_success:
                print(value)
            else:
                print("Found EDD path: " + value)
                edd_device_mapping = value

        if edd_device_mapping == "":
            is_success, value = ChsUtilities.find_edd_sysfs_path_using_disk_capacity(long_device_node, logger)
            if not is_success:
                print(value)
            else:
                print("Found EDD path: " + value)
                edd_device_mapping = value

        if edd_device_mapping == "":
            return False, "Could not determine EDD mapping"

        legacy_max_head_absolute_path = os.path.join("/sys/firmware/edd/", edd_device_mapping, "legacy_max_head")
        if not os.path.isfile(legacy_max_head_absolute_path):
            return False, "Does not exist: " + legacy_max_head_absolute_path
        raw_head = int(Utility.read_file_into_string(legacy_max_head_absolute_path)) + 1

        legacy_sectors_per_track_absolute_path = os.path.join("/sys/firmware/edd/", edd_device_mapping,
                                                              "legacy_sectors_per_track")
        if not os.path.isfile(legacy_sectors_per_track_absolute_path):
            return False, "Does not exist: " + legacy_sectors_per_track_absolute_path
        raw_sector = int(Utility.read_file_into_string(legacy_sectors_per_track_absolute_path))

        # "# Orgad Shaneh mentioned that the cylinders value from legacy_max_cylinder is WRONG. It is limited to
        # 1022 or something like that. The actual cylinders value must be calculated as a division result."
        # "Ref: https://sourceforge.net/p/clonezilla/discussion/Help/thread/e5dbb91b/"

        sectors_absolute_path = os.path.join("/sys/firmware/edd/", edd_device_mapping, "sectors")
        if not os.path.isfile(sectors_absolute_path):
            return False, "Does not exist: " + sectors_absolute_path
        sectors_from_edd = int(Utility.read_file_into_string(sectors_absolute_path))

        if str(sectors_from_edd) != "" and str(raw_head) != "" and str(raw_sector) != "":
            print("Clonezilla would compute cylinders (in Bash): $((" + str(sectors_from_edd) + "/" + str(raw_head) + "/" + str(raw_sector) + "))")
            # Bash division appears to truncate/floor the information after decimal, so Rescuezilla emulates this here.
            # TODO: Re-evaluate if this is the best approach.
            raw_cylinder = math.floor(math.floor(sectors_from_edd / raw_head) / raw_sector)
        else:
            return False, "Invalid values sectors_from_edd: " + str(sectors_from_edd) + ", raw_head: " + str(
                raw_head) + ", raw_sector: " + str(raw_sector)

        if raw_head == 0 or raw_sector == 0:
            return False, "No head or sector number of " + long_device_node + " was found from EDD info."
        else:
            return True, {'cylinders': raw_cylinder, 'heads': raw_head, 'sectors': raw_sector}

    # Query the EDD (Enhanced Disk Device) sysfs path (/sys/firmware/edd/...) by first querying the 32-bit MBR disk
    # signature.
    #
    # This function is a port of Clonezilla's edd_id_map_by_mbr function from sbin/ocs-functions file, which references
    # [1] http://en.wikipedia.org/wiki/Master_boot_record
    #
    # TODO: Revisit this, because there's likely a better way to do this than how Clonezilla does it.
    @staticmethod
    def _find_edd_sysfs_path_using_mbr_disk_signature(long_device_node, logger):
        if not os.path.exists(long_device_node):
            # Unclear why Clonezilla checks this.
            return False, "Does not exist:" + long_device_node
        process, flat_command_string, failed_message = Utility.run("Get edd device mapping)",
                                                                   ["hexdump", "-n", "4", "-s", "440",
                                                                    "-e", '"0x%.8x\\n"', long_device_node],
                                                                   use_c_locale=True, logger=logger)
        if process.returncode == 0 and len(process.stdout) > 0:
            mbr_signature_to_find = process.stdout
            edd_mbr_signature_glob_list = glob.glob("/sys/firmware/edd/int13_*/mbr_signature")
            for edd_mbr_signature_absolute_path in edd_mbr_signature_glob_list:
                # MBR signature file is in ASCII
                mbr_signature = Utility.read_file_into_string(edd_mbr_signature_absolute_path)
                if mbr_signature_to_find.strip() == mbr_signature.strip():
                    return True, os.path.dirname(edd_mbr_signature_absolute_path)
        return False, "Could not find sysfs EDD for " + long_device_node + " using MBR signature"

    # Query the EDD (Enhanced Disk Device) sysfs path (/sys/firmware/edd/...) by searching for the disk capacity as the
    # search query.
    #
    # This function is a port of Clonezilla's edd_id_map_by_capacity function from sbin/ocs-functions file
    #
    # TODO: Revisit this, because there's likely a better way to do this than how Clonezilla does it.
    @staticmethod
    def find_edd_sysfs_path_using_disk_capacity(long_device_node, logger):
        sysblock_name = ChsUtilities.to_sysblock_name(long_device_node)
        sysfs_disk_capacity_absolute_path = os.path.join("/sys/block/", sysblock_name, "size")
        if not os.path.isfile(sysfs_disk_capacity_absolute_path):
            return False, "Does not exist: " + sysfs_disk_capacity_absolute_path
        sysfs_disk_capacity_string = Utility.read_file_into_string(sysfs_disk_capacity_absolute_path)

        edd_sectors_glob_list = glob.glob("/sys/firmware/edd/int13_*/sectors")
        for edd_sectors_absolute_path in edd_sectors_glob_list:
            # Sectors file is ASCII
            sector_string = Utility.read_file_into_string(edd_sectors_absolute_path)
            if sysfs_disk_capacity_string.strip() == sector_string.strip():
                return True, os.path.dirname(edd_sectors_absolute_path)
        return False, "Could not find sysfs EDD for " + long_device_node + " using capacity " + sysfs_disk_capacity_string

    # Clonezilla's to_sysblock_name
    # "Function to convert /sys/ file name, e.g. the cciss/c0d0 file name under /sys is /sys/block/cciss!c0d0/size
    # We have convert to /sys/block/cciss!c0d0/size"
    @staticmethod
    def to_sysblock_name(long_device_node):
        short_device_node = re.sub('/dev/', '', long_device_node)
        sysblock_device_node = re.sub('/', '!', short_device_node)
        return sysblock_device_node
