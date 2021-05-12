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
import utility

class ProcPartitions:
    # Clonezila's "wait_for_part_table_take_effect" polls `$(grep -Ew "${dsk_}p*[[:digit:]]+" /proc/partitions)`
    # for 50 times (once every 0.2 seconds), until the output of that command is non-zero (ie "sda1" or "nvme0n1p1")
    # has been populated.
    #
    # This function intends to achieve a similar outcome. See unit test for example cases.
    @staticmethod
    def are_partitions_listed_in_proc_partitions(proc_partitions_string, short_device_node):
        for line in proc_partitions_string.splitlines():
            m = utility.REMatcher(line)
            if m.match(r".*" + short_device_node + r"[p]+[0-9]+$"):
                return True
        return False