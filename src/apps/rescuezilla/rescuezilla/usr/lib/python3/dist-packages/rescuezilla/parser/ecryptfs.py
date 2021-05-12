# ----------------------------------------------------------------------
#   Copyright (C) 2003-2021 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2020-2021 Rescuezilla.com <rescuezilla@gmail.com>
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
class Ecryptfs:
    # Processes Clonezilla's ecryptfs.info metadata file. See unit test for full example
    @staticmethod
    def parse_ecryptfs_info(ecryptfs_info_string):
        ecryptfs_info_dict = {}
        lines = ecryptfs_info_string.splitlines()
        for line in lines:
            if not line.startswith("#"):
                split = line.split("=")
                key = split[0].strip()
                value = split[1].strip()
                value = value.strip('"')
                if key == "disk_of_img":
                    value_list = value.split(" ")
                    ecryptfs_info_dict["disk"] = value_list
                elif key == "parts_of_img":
                    value_list = value.split(" ")
                    ecryptfs_info_dict["parts"] = value_list
                elif key == "time_of_img":
                    # TODO: Process this time value rather than keeping it as a string
                    ecryptfs_info_dict["time"] = value
                elif key == "disks_size_all_of_img":
                    # TODO: Process this size value rather than keeping it as a string
                    ecryptfs_info_dict["size"] = value
                else:
                    print("Unexpected ecryptfs.info line" + line)
                    ecryptfs_info_dict[key] = value
        return ecryptfs_info_dict
