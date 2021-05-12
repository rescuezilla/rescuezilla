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
import unittest

from parser.os_prober import OsProber


class OsProberTest(unittest.TestCase):
    def test_os_prober_parsing(self):
        os_prober_contents = """/dev/sdc2@/efi/Microsoft/Boot/bootmgfw.efi:Windows Boot Manager:Windows:efi
/dev/sdd1:Debian GNU/Linux 10 (buster):Debian:linux"""
        osprober_dict = OsProber.parse_os_prober_output(os_prober_contents)
        print("Actual osprober dict is " + str(osprober_dict))
        expected_osprober_dict = collections.OrderedDict([
            ('/dev/sdc2', {'os_description': 'Windows Boot Manager',  'os_label': 'Windows', 'os_type': 'efi', 'efi_bootloader_path': "/efi/Microsoft/Boot/bootmgfw.efi"}),
            ('/dev/sdd1', {'os_description':  'Debian GNU/Linux 10 (buster)', 'os_label': 'Debian', 'os_type': 'linux'})])
        self.assertDictEqual(expected_osprober_dict, osprober_dict)
