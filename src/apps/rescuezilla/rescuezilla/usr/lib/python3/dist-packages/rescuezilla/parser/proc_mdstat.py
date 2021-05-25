# ----------------------------------------------------------------------
#   Copyright (C) 2003-2021 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2021 Rescuezilla.com <rescuezilla@gmail.com>
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

# Port of Clonezilla's "dump_software_raid_info_if_exists" function
class ProcMdstat:
    # Clonezilla's "dump_software_raid_info_if_exists" searches /proc/mdstat for active RAID volumes and
    # saves statistics. This function just processes the /proc/mdstat file into a list of active RAID devices nodes
    #
    # See unit test for example cases.
    @staticmethod
    def parse_proc_mdstat_string(proc_mdstat_stringe):
        proc_mdstat_dict = {}
        for line in proc_mdstat_stringe.splitlines():
            m = utility.REMatcher(line)
            if m.match(r"Personalities : ([.*])"):
                # TODO: Process further. If required
                proc_mdstat_dict['personalities'] = m.group(1)
                continue
            elif m.match(r"([a-zA-Z0-9]+) : active.*"):
                md_device = m.group(1)
                # TODO: Process further. If required
                proc_mdstat_dict[md_device] = line
            else:
                print("Not processing line" + line)
        return proc_mdstat_dict