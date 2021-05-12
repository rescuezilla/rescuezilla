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
import pprint
import unittest

from parser.ecryptfs import Ecryptfs
from parser.swappt import Swappt


class SwapptInfoTest(unittest.TestCase):
    def test_extracting_short_device_node_from_swappt_info_filename(self):
        input_swappt_info_filename = "/path/to/swappt-sda12.info"
        swappt_short_device_node = Swappt.get_short_device_from_swappt_info_filename(input_swappt_info_filename)
        expected_short_device_node = "sda12"
        self.assertEqual(expected_short_device_node, swappt_short_device_node)

        input_swappt_info_filename = "/path/to/swappt-testvg-testlv.info"
        swappt_short_device_node = Swappt.get_short_device_from_swappt_info_filename(input_swappt_info_filename)
        expected_short_device_node = "testvg-testlv"
        self.assertEqual(expected_short_device_node, swappt_short_device_node)

    def test_swaptpt_info_parsing(self):
        input_swappt_info_string = """UUID="TEST-UUID-VALUE123"
LABEL="TEST_LABEL" """
        swappt_info_dict = Swappt.parse_swappt_info(input_swappt_info_string)

        expected_swappt_info_dict = {
            'uuid': "TEST-UUID-VALUE123",
            "label": "TEST_LABEL"
        }
        self.assertDictEqual(expected_swappt_info_dict, swappt_info_dict)
