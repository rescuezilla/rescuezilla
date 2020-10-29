#!/usr/bin/python3
# ----------------------------------------------------------------------
#   Rescuezilla Image Explorer
#   A simple GUI interface to explorer backup images
#   https://www.patreon.com/join/rescuezilla
# ----------------------------------------------------------------------
#   Copyright (C) 2012 RedoBackup.org
#   Copyright (C) 2019-2020 Rescuezilla.com <rescuezilla@gmail.com>
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
import rescuezilla


# Wrapper function to launch Rescuezilla Image Explorer GUI. The different process name allows GParted
# or standard Rescuezilla GUI to run alongside Image Explorer without triggering mutual exclusion.
def main():
    rescuezilla.main(is_image_explorer_mode=True)


if __name__ == "__main__":
    main()
