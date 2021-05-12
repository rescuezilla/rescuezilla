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
import collections
import json
import math


class Lsblk:
    @staticmethod
    def parse_lsblk_json_output(lsblk_json_output):
        unnested_lsblk_dict = collections.OrderedDict([])
        lsblk_json_dict = json.loads(lsblk_json_output)
        print("output is " + str(lsblk_json_dict))
        block_device_dict_list_to_process = lsblk_json_dict['blockdevices']
        while len(block_device_dict_list_to_process) > 0:
            block_device_dict = block_device_dict_list_to_process.pop()
            print("Processing " + str(block_device_dict))
            if 'children' in block_device_dict.keys():
                block_device_dict_list_to_process += block_device_dict['children']
                del block_device_dict['children']
            if 'name' in block_device_dict.keys():
                name = block_device_dict.pop('name', None)
                unnested_lsblk_dict[name] = block_device_dict
            else:
                print("Unknown")
        return unnested_lsblk_dict

    # This function is not used, but kept for for evaluation and discussion. See unit test for more information.
    @staticmethod
    def parse_lsblk_output(lsblk_output):
        unnested_lsblk_dict = collections.OrderedDict([])
        lines = lsblk_output.split(sep="\n")
        column_title = lines.pop(0)
        #print("Column title is" + column_title)
        kname_index = column_title.index("KNAME")
        name_index = column_title.index(" NAME") + 1
        # The size column is right justified, so the start index needs to be carefully calculated (see unit test)
        index_of_space_after_e_in_name = name_index + 4
        index_of_space_before_s_in_size = column_title.index("SIZE") - 1
        size_index = math.ceil((index_of_space_after_e_in_name + index_of_space_before_s_in_size) / 2)
        type_index = column_title.index("TYPE")
        fstype_index = column_title.index("FSTYPE")
        mountpoint_index = column_title.index("MOUNTPOINT")
        model_index = column_title.index("MODEL")
        for line in lines:
            name = line[name_index:size_index].strip().lstrip('├─').lstrip('└─')
            unnested_lsblk_dict[name] = {}
            # Maybe able to have deeper nested structures.
            unnested_lsblk_dict[name]['kname'] = line[kname_index:name_index - 1].strip()
            unnested_lsblk_dict[name]['size'] = line[size_index:type_index - 1].strip()
            unnested_lsblk_dict[name]['type'] = line[type_index:fstype_index - 1].strip()
            unnested_lsblk_dict[name]['fstype'] = line[fstype_index:mountpoint_index - 1].strip()
            unnested_lsblk_dict[name]['mountpoint'] = line[mountpoint_index:model_index - 1].strip()
            unnested_lsblk_dict[name]['model'] = line[model_index:len(line)].strip()
        return unnested_lsblk_dict
