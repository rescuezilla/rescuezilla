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
import collections
import subprocess

import utility


class Partclone:
    @staticmethod
    def parse_partclone_output(line):
        temp_dict = {}
        m = utility.REMatcher(line)
        if line.strip() == "":
            # Ignore
            return temp_dict
        elif line.startswith("Device size") or line.startswith("Space in use") or line.startswith("Free Space") or line.startswith("Block size") or line.startswith("done!"):
            temp_dict['status'] = line
            return temp_dict
        elif line.startswith("Calculating"):
            temp_dict['status'] = line
            return temp_dict
        # Processing: Elapsed: 00:01:38, Remaining: 00:00:28, Completed:  77.58%,   2.57MB/min,
        elif m.match(
                r"\s*Elapsed:\s*([0-9]*:[0-9]*:[0-9]*),\s*Remaining:\s*([0-9]*:[0-9]*:[0-9]*),\s*Completed:\s*([0-9]*\.[0-9]*)%,\s*[Rate:]*\s*([0-9]*\.[0-9]\w*/min).*"):
            temp_dict['elapsed'] = m.group(1)
            temp_dict['remaining'] = m.group(2)
            temp_dict['completed'] = float(m.group(3))
            temp_dict['rate'] = m.group(4)
            return temp_dict
        # Processing: current block:     121264, total block:     240127, Complete: 100.00%
        elif m.match(r"\s*current\sblock:\s*([0-9]*),\s*total\sblock:\s*([0-9]*),\s*Complete:\s*([0-9]*\.[0-9]*)%"):
            temp_dict['current_block'] = m.group(1)
            temp_dict['total_block'] = m.group(2)
            temp_dict['completed_block_percent'] = m.group(3)
            return temp_dict
        elif line.startswith("Cloned"):
            temp_dict['status'] = line
            return temp_dict
        else:
            print("Not yet interpreting partclone output: " + line)
            return temp_dict

    # Extracts information from `partclone.info`. This information only provides an indication of the filesystem,
    # Partclone's ability to detect filesystem information from an image is not guaranteed to be reliable.
    @staticmethod
    def parse_partclone_info_output(partclone_info_output):
        partclone_info_dict = collections.OrderedDict([])
        for line in partclone_info_output.splitlines():
            if line.strip() == "":
                continue
            elif line.startswith("Partclone v"):
                # Ignore the line Partclone v0.3.13 http://partclone.org
                continue
            elif line.startswith("Showing info of image (-)"):
                # Ignore the line
                continue
            else:
                m = utility.REMatcher(line)
                if m.match("File system:\s+([a-zA-Z0-9+]+)"):
                    partclone_info_dict['filesystem'] = m.group(1)
                elif m.match(r"Device size:\s+([a-zA-Z0-9+\s\.]+) = ([0-9]+) Blocks"):
                    partclone_info_dict['size'] = {
                        'enduser_readable': m.group(1),
                        'blocks': int(m.group(2).strip()),
                    }
                elif m.match(r"Space in use:\s+([a-zA-Z0-9+\s\.]+) = ([0-9]+) Blocks"):
                    partclone_info_dict['used_space'] = {
                        'enduser_readable': m.group(1),
                        'blocks': int(m.group(2).strip()),
                    }
                elif m.match(r"Free Space:\s+([a-zA-Z0-9+\s\.]+) = ([0-9]+) Blocks"):
                    partclone_info_dict['free_space'] = {
                        'enduser_readable': m.group(1),
                        'blocks': int(m.group(2).strip()),
                    }
                elif m.match("Block size:\s+([0-9+]+)"):
                    partclone_info_dict['block_size'] = int(m.group(1))
                elif m.match(r"image format:\s+([0-9a-zA-Z/]+)"):
                    partclone_info_dict['image_format'] = m.group(1)
                elif m.match(r"created on a:\s+([a-zA-Z/]+)"):
                    partclone_info_dict['created'] = m.group(1)
                elif m.match(r"with partclone:\s+([a-zA-Z/]+)"):
                    partclone_info_dict['with_partclone'] = m.group(1)
                elif m.match(r"bitmap mode:\s+([a-zA-Z/]+)"):
                    partclone_info_dict['bitmap_mode'] = m.group(1)
                elif m.match(r"checksum algo:\s+([a-zA-Z0-9_/]+)"):
                    partclone_info_dict['checksum_algo'] = m.group(1)
                elif m.match(r"checksum size:\s+([0-9]+)"):
                    partclone_info_dict['checksum_size'] = int(m.group(1))
                elif m.match(r"blocks/checksum:\s+([0-9]+)"):
                    partclone_info_dict['blocks/checksum'] = int(m.group(1))
                elif m.match(r"reseed checksum:\s+([a-zA-Z]+)"):
                    partclone_info_dict['reseed_checksum'] = "False"
                else:
                    print("Not yet interpreting partclone output: " + line)

        # Calculate the byte sizes for partition size, used space and free space.
        if 'block_size' in partclone_info_dict.keys():
            bs = partclone_info_dict['block_size']
            if 'size' in partclone_info_dict.keys():
                partclone_info_dict['size']['bytes'] = bs * partclone_info_dict['size']['blocks']
            if 'free_space' in partclone_info_dict.keys():
                partclone_info_dict['free_space']['bytes'] = bs * partclone_info_dict['free_space']['blocks']
            if 'used_space' in partclone_info_dict.keys():
                partclone_info_dict['used_space']['bytes'] = bs * partclone_info_dict['used_space']['blocks']
        return partclone_info_dict

    @staticmethod
    def get_partclone_info_dict(abs_partclone_image_list, image_key, compression):
        env = utility.Utility.get_env_C_locale()
        proc = collections.OrderedDict()
        cat_cmd_list = ["cat"] + abs_partclone_image_list
        decompression_cmd_list = utility.Utility.get_decompression_command_list(compression)
        partclone_info_cmd_list = ["partclone.info", "--source", "-"]
        utility.Utility.print_cli_friendly("partclone ", [cat_cmd_list, decompression_cmd_list, partclone_info_cmd_list])
        proc['cat_partclone' + image_key] = subprocess.Popen(cat_cmd_list, stdout=subprocess.PIPE, env=env,
                                                                          encoding='utf-8')
        proc['decompression' + image_key] = subprocess.Popen(decompression_cmd_list,
                                                                          stdin=proc[
                                                                              'cat_partclone' + image_key].stdout,
                                                                          stdout=subprocess.PIPE, env=env, encoding='utf-8')
        proc['partclone_info' + image_key] = subprocess.Popen(partclone_info_cmd_list,
                                                                           stdin=proc[
                                                                               'decompression' + image_key].stdout,
                                                                           stdout=subprocess.PIPE,
                                                                           stderr=subprocess.PIPE, env=env,
                                                                           encoding='utf-8')
        proc['cat_partclone' + image_key].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
        proc['decompression' + image_key].stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
        output, err = proc['partclone_info' + image_key].communicate()
        print("partclone_info: Exit output " + str(output) + "stderr " + str(err))
        partclone_info_dict = Partclone.parse_partclone_info_output(err)
        if len(partclone_info_dict) == 0:
            # If unable to read the partclone.info output, treat this as a dd image (see unit test for
            # partclone.info example output for this case).
            print(abs_partclone_image_list[0] + ": Could not read partclone info dict for " + image_key + ". Treating it as a dd image.")
            partclone_info_dict['filesystem'] = "<unknown>"
        return partclone_info_dict