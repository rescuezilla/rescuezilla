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
import os

import utility


class Swappt:
    # Extract 'sdf11' from /path/to/swappt-sdf11.info
    @staticmethod
    def get_short_device_from_swappt_info_filename(swap_partition_info_abs_path):
        m = utility.REMatcher(os.path.basename(swap_partition_info_abs_path))
        if m.match("swappt-([a-zA-Z0-9-+_]+).info"):
            short_device_node = m.group(1)
        else:
            raise Exception("Unable to extract short device node from " + swap_partition_info_abs_path)
        return short_device_node

    @staticmethod
    def parse_swappt_info(swappt_info_string):
        swappt_info_dict = {}
        lines = swappt_info_string.splitlines()
        for line in lines:
            split = line.split("=")
            key = split[0].strip()
            value = split[1].strip()
            value = value.strip('"')
            if key == "UUID":
                swappt_info_dict["uuid"] = value
            elif key == "LABEL":
                swappt_info_dict["label"] = value
            else:
                print("Unexpected data in swap partition info file " + line)
                swappt_info_dict[key] = value
        return swappt_info_dict
