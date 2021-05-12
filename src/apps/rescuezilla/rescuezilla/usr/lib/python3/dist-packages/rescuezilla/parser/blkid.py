# ----------------------------------------------------------------------
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
import collections


class Blkid:
    @staticmethod
    def parse_blkid_output(blkid_output):
        blkid_dict = collections.OrderedDict([])
        blkid_list = blkid_output.splitlines()
        for blkid_line in blkid_list:
            split = blkid_line.split(sep=":", maxsplit=1)
            #print("Analysing " + str(split))
            long_dev_node = split[0]
            key_value_list = split[1].strip().split(sep='" ')
            blkid_dict[long_dev_node] = {}
            for key_value in key_value_list:
                #print("Analysing key/value " + key_value)
                key_value_split = key_value.split(sep="=")
                key = key_value_split[0]
                value = key_value_split[1].strip('"')
                blkid_dict[long_dev_node][key] = value
        return blkid_dict
