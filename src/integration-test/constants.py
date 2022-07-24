#!/usr/bin/python3
# ----------------------------------------------------------------------
#   Rescuezilla Integration Test Suite constants
# ----------------------------------------------------------------------
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
import os
from pathlib import Path

HOST_SHARED_FOLDER = "/mnt/rescuezilla.shared.folder"
CHECK_SOCKET=9999
VIRTUAL_BOX_FOLDER = os.path.join(Path.home(), "VirtualBox VMs/Rescuezilla.Integration.Test.Suite.VDIs")

# Note: VirtualBox doesn't provide any way to create a specific interface. It create increments until the first unused interface
VIRTUAL_BOX_HOSTONLYIFS="vboxnet0"

DRIVE_DICT = {
    'image.repository': {'size_gigabyte': 12*1024, 'uuid': "00000000-0000-0000-0000-000000000001"},
    '1gb': {'size_gigabyte': 1, 'uuid': "11111111-1111-1111-1111-111111111111"},
    '2gb': {'size_gigabyte': 2, 'uuid': "22222222-2222-2222-2222-222222222222"},
    '8gb': {'size_gigabyte': 8, 'uuid': "88888888-8888-8888-8888-888888888888"},
    '16gb': {'size_gigabyte': 16, 'uuid': "16161616-1616-1616-1616-161616161616"},
    '50gb': {'size_gigabyte': 50, 'uuid': "50505050-5050-5050-5050-505050505050"},
    '2tb.primary': {'size_gigabyte': 2048, 'uuid': "00000000-2048-0000-0000-000000000000"},
    '2tb.secondary': {'size_gigabyte': 2048, 'uuid': "22222222-2048-2222-2222-222222222222"},
    '1.9tb': {'size_gigabyte': 1949, 'uuid': "19491949-1949-1949-1949-194919491949"},
}

MACHINE_DICT = {"Rescuezilla.Development": {
    'hd_list': ['image.repository', '1gb', '2gb', '8gb', '16gb', '50gb', '2tb.primary', '2tb.secondary',
                '1.9tb'], 'firmware': "bios", 'ip': "192.168.60.2"},
    "Rescuezilla.Integration.Test.Suite.Controller": {
        'hd_list': ['image.repository', '1gb', '2gb', '8gb', '16gb', '50gb', '2tb.primary', '2tb.secondary',
                    '1.9tb'], 'firmware': "bios", 'ip': "192.168.60.3"},
    "Rescuezilla.8gb.BIOS": {'hd_list': ['8gb'], 'firmware': "bios", 'ip': "192.168.60.100"},
    "Rescuezilla.8gb.EFI": {'hd_list': ['8gb'], 'firmware': "efi64", 'ip': "192.168.60.101"},
    "Rescuezilla.16gb.BIOS": {'hd_list': ['16gb'], 'firmware': "bios", 'ip': "192.168.60.102"},
    "Rescuezilla.50gb.BIOS": {'hd_list': ['50gb'], 'firmware': "bios", 'ip': "192.168.60.103"},
    "Rescuezilla.50gb.EFI": {'hd_list': ['50gb'], 'firmware': "efi64", 'ip': "192.168.60.104"},
    "Rescuezilla.2tb.Primary.BIOS": {'hd_list': ['2tb.primary'], 'firmware': "bios", 'ip': "192.168.60.105"},
    "Rescuezilla.2tb.Primary.EFI": {'hd_list': ['2tb.primary'], 'firmware': "efi64", 'ip': "192.168.60.106"},
    "Rescuezilla.2tb.Secondary.BIOS": {'hd_list': ['2tb.secondary'], 'firmware': "bios", 'ip': "192.168.60.107"},
    "Rescuezilla.2tb.Secondary.EFI": {'hd_list': ['2tb.secondary'], 'firmware': "efi64", 'ip': "192.168.60.108"},
    "Rescuezilla.1.9tb.BIOS": {'hd_list': ['1.9tb'], 'firmware': "bios", 'ip': "192.168.60.109"},
    "Rescuezilla.1.9tb.EFI": {'hd_list': ['1.9tb'], 'firmware': "bios", 'ip': "192.168.60.110"}
}

# Preprepared VDI images that can be copied in, for ease of testing.
DEPLOY_DICT = {
    "deploy_repo": "/mnt/vdi/",
    "8gb": "8gb.Debian.Encrypted.vdi",
    "16gb": "16gb.CentOS.MBR.vdi",
    "50gb": "50gb.Windows.GPT.vdi",
    "2tb.primary": "2tb.MBR.Windows.By.Itself.vdi",
    "2tb.secondary": "2tb.MBR.Windows.Ubuntu.DualBoot.vdi",
    "1.9tb": "1tb.MBR.compressed.BTRFS.Fedora.Workstation.36.vdi",
}
