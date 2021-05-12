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

import collections
import re


class OsProber:
    @staticmethod
    def parse_os_prober_output(os_prober_output):
        """Converts the STDOUT of os-prober into a dictionary. See unit tests for a complete example"""
        os_dict = collections.OrderedDict([])
        split_lines = os_prober_output.splitlines()
        for os_entry in split_lines:
            # Split input string into a two element list using the *second* heading
            os_line = re.split(":", os_entry)
            try:
                efi_split = re.split("@", os_line[0])
                longdevname = efi_split[0]
                os_dict[longdevname] = {'os_description': os_line[1], 'os_label': os_line[2], 'os_type': os_line[3]}
                try:
                    efi_bootloader_path = efi_split[1]
                    os_dict[longdevname]['efi_bootloader_path'] = efi_bootloader_path
                except IndexError:
                    continue
                    # To be expected
                    # print("Did not detect @ split EFI path: " + str(os_entry))
            except IndexError:
                print("Unable to parse: " + str(os_entry) + ". Skipping")
        print("os_dict:" + str(os_dict))
        return os_dict
