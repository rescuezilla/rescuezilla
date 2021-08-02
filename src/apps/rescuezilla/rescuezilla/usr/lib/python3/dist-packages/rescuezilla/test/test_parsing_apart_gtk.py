# ----------------------------------------------------------------------
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
import pprint
import unittest

from parser.apart_gtk_image import ApartGtkImage


class ApartGtkTest(unittest.TestCase):
    def test_apart_gtk_parsing(self):
        pp = pprint.PrettyPrinter(indent=4)
        # Filenames taken from the Apart GTK demonstration video
        boot_filename = "boot-2017-05-06T1641.apt.ext2.gz"
        expected_boot_dict = {
            'name': "boot",
            'timestamp': "2017-05-06T1641",
            'filesystem': "ext2",
            'compression': "gz",
            'inprogress': False
        }
        actual_boot_dict = ApartGtkImage._parse_filename(boot_filename)
        pp.pprint(actual_boot_dict)
        self.assertDictEqual(expected_boot_dict, actual_boot_dict)

        swap_filename = "swap-2017-05-06T1641.apt.dd.gz"
        expected_swap_dict = {
            'name': "swap",
            'timestamp': "2017-05-06T1641",
            'filesystem': "dd",
            'compression': "gz",
            'inprogress': False
        }
        actual_swap_dict = ApartGtkImage._parse_filename(swap_filename)
        self.assertDictEqual(expected_swap_dict, actual_swap_dict)

        main_usb_filename = "main-usb-2017-05-06T1641.apt.f2fs.gz"
        expected_main_usb_dict = {
            'name': "main-usb",
            'timestamp': "2017-05-06T1641",
            'filesystem': "f2fs",
            'compression': "gz",
            'inprogress': False
        }
        actual_main_usb_dict = ApartGtkImage._parse_filename(main_usb_filename)
        self.assertDictEqual(expected_main_usb_dict, actual_main_usb_dict)

        inprogress_test_filename = "main-usb-2017-05-06T1641.apt.f2fs.gz.inprogress"
        expected_main_usb_dict['inprogress'] = True
        actual_inprogress_dict = ApartGtkImage._parse_filename(inprogress_test_filename)
        self.assertDictEqual(expected_main_usb_dict, actual_inprogress_dict)
