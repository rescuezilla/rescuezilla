#!/usr/bin/python3
# ----------------------------------------------------------------------
#   Rescuezilla Integration Test Suite
#   For an introduction, see src/integration-test/README.md
# ----------------------------------------------------------------------
#   Copyright (C) 2021 Patrick Rouleau <pfrouleau@gmail.com>
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
import re
import shutil
import socket
import subprocess
import argparse
import sys
from pathlib import Path
from time import sleep

from constants import DRIVE_DICT, MACHINE_DICT, VIRTUAL_BOX_FOLDER, DEPLOY_DICT, VIRTUAL_BOX_HOSTONLYIFS, CHECK_SOCKET, \
    HOST_SHARED_FOLDER


# Create VMs
def initialize_vms(hd_key_list, machine_key_list):
    if not os.path.isdir(HOST_SHARED_FOLDER):
        print("Cannot find: " + HOST_SHARED_FOLDER)
        print("First create it with: sudo mkdir " + HOST_SHARED_FOLDER)
        exit()

    print("Removing host-only interface: " + VIRTUAL_BOX_HOSTONLYIFS)
    remove_hostonlyif_cmd_list = ["VBoxManage", "hostonlyif", "remove", VIRTUAL_BOX_HOSTONLYIFS]
    subprocess.run(remove_hostonlyif_cmd_list, encoding='utf-8')

    print("Add new host-only interface, which will automatically populate lowest free interface, ie " + VIRTUAL_BOX_HOSTONLYIFS)
    hostonlyif_create_cmd_list = ["VBoxManage", "hostonlyif", "create"]
    subprocess.run(hostonlyif_create_cmd_list, encoding='utf-8')

    print("Set IP address on VirtualBox DHCP server" + VIRTUAL_BOX_HOSTONLYIFS)
    hostonlyif_create_cmd_list = ["VBoxManage", "hostonlyif", "ipconfig", VIRTUAL_BOX_HOSTONLYIFS, "--ip", "192.168.60.1", "--netmask", "255.255.255.0"]
    subprocess.run(hostonlyif_create_cmd_list, encoding='utf-8')

    print("Add dhcp server on interface: " + VIRTUAL_BOX_HOSTONLYIFS)
    add_dhcp_server_cmd_list = ["VBoxManage", "dhcpserver", "add", "--interface", VIRTUAL_BOX_HOSTONLYIFS,
                                "--server-ip", "192.168.60.1", "--netmask", "255.255.255.0", "--lower-ip",
                                "192.168.60.2", "--upper-ip", "192.168.60.200", "--enable"]
    subprocess.run(add_dhcp_server_cmd_list, encoding='utf-8')

    for hd_prefix in hd_key_list:
        create_hd(hd_prefix, DRIVE_DICT[hd_prefix]['size_gigabyte'])

    for vm_name in machine_key_list:
        create_vm(vm_name, hd_key_list)


def deinitialize_vms(hd_key_list, machine_key_list):
    print("Remove DHCP server associated with host-only interface " + VIRTUAL_BOX_HOSTONLYIFS)
    remove_dhcpserver_cmd_list = ["VBoxManage", "dhcpserver", "remove", "--interface", VIRTUAL_BOX_HOSTONLYIFS]
    subprocess.run(remove_dhcpserver_cmd_list, encoding='utf-8')

    print("Remove host-only interface: " + VIRTUAL_BOX_HOSTONLYIFS)
    remove_hostonlyif_cmd_list = ["VBoxManage", "hostonlyif", "remove", VIRTUAL_BOX_HOSTONLYIFS]
    subprocess.run(remove_hostonlyif_cmd_list, encoding='utf-8')

    for vm_name in machine_key_list:
        print("Removing " + vm_name)
        sata_port = 0
        for hd_prefix in MACHINE_DICT[vm_name]['hd_list']:
            if hd_prefix in hd_key_list:
                print(" Detaching " + hd_prefix + ".vdi")
                # Detach drive by inserting 'none' device
                detach_storage_cmd_list = ["VBoxManage", "storageattach", vm_name, "--storagectl", "SATA Controller",
                                           "--port", str(sata_port), "--device", "0", "--type", "hdd", "--medium",
                                           "none"]
                subprocess.run(detach_storage_cmd_list, encoding='utf-8')
                sata_port += 1
                # Remove
                # remove_hdd_cmd_list = ["VBoxManage", "storagectl", vm_name, "--name", hd_prefix + ".vdi", "--remove"]
                # subprocess.run(remove_hdd_cmd_list, encoding='utf-8')
            else:
                sata_port += 1
                continue

        # Delete VM
        delete_vm_cmd_list = ["VBoxManage", "unregistervm", vm_name, "--delete"]
        subprocess.run(delete_vm_cmd_list, encoding='utf-8')

        for hd_prefix in MACHINE_DICT[vm_name]['hd_list']:
            if hd_prefix not in hd_key_list:
                continue
            # Attempt to delete drive if it's not attached to any other VMs
            delete_hdd_cmd_list = ["VBoxManage", "closemedium", "disk", hd_prefix + ".vdi", "--delete"]
            subprocess.run(delete_hdd_cmd_list, encoding='utf-8')

            original_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".vdi")
            zeroed_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".zeroed.vdi")
            if (not os.path.isfile(original_hd)) and os.path.isfile(zeroed_hd):
                print("Removing " + zeroed_hd)
                os.remove(zeroed_hd)


def deploy_hd(hd_prefix_list):
    for hd_prefix in hd_prefix_list:
        if hd_prefix in DEPLOY_DICT.keys():
            original_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".vdi")
            deploy_hd = os.path.join(DEPLOY_DICT['deploy_repo'], DEPLOY_DICT[hd_prefix])

            if not os.path.isfile(deploy_hd):
                print("Could not find " + deploy_hd)
                continue
            else:
                # Copy in hard drive
                print("Copying " + deploy_hd + " to " + original_hd + ". This may take some time...")
                subprocess.run(["rsync", "-aP", deploy_hd, original_hd])

            # Update VirtualBox UUID of newly copied in hard drive
            set_uuid_cmd_list = ["VBoxManage", "internalcommands", "sethduuid", original_hd, DRIVE_DICT[hd_prefix]['uuid']]
            subprocess.run(set_uuid_cmd_list, encoding='utf-8')


def reset_hd(hd_prefix_list):
    for hd_prefix in hd_prefix_list:
        original_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".vdi")
        zeroed_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".zeroed.vdi")
        if not os.path.exists(zeroed_hd):
            print("Does not exist " + zeroed_hd, file=sys.stderr)
        else:
            print("Restoring " + zeroed_hd + " to " + original_hd)
            shutil.copyfile(zeroed_hd, original_hd)


def commit_hd(hd_prefix_list, do_overwrite):
    if not do_overwrite:
        print("Warning: committing means overwriting the saved images in " + DEPLOY_DICT[
            'deploy_repo'] + " with the files in " + VIRTUAL_BOX_FOLDER)
        print("This is a potentially a dangerous operation as the files in " + VIRTUAL_BOX_FOLDER + " may be empty.)")
        print("Provide --force to confirm that you want to overwrite.")

    for hd_prefix in hd_prefix_list:
        if hd_prefix in DEPLOY_DICT.keys():
            deploy_hd = os.path.join(DEPLOY_DICT['deploy_repo'], DEPLOY_DICT[hd_prefix])
            original_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".vdi")
            if not os.path.exists(original_hd):
                print("Does not exist " + original_hd, file=sys.stderr)
            else:
                print("Copying " + original_hd + " to " + deploy_hd + ". This may take a while...")
                if do_overwrite:
                    subprocess.run(["rsync", "-aP", original_hd, deploy_hd])
                else:
                    print("  Skipping because --force not provided.")


def create_hd(hd_prefix, size_gigabyte):
    size_byte = size_gigabyte * 1024 * 1024 * 1024
    original_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".vdi")
    zeroed_hd = os.path.join(VIRTUAL_BOX_FOLDER, hd_prefix + ".zeroed.vdi")
    if os.path.isfile(original_hd):
        print("File exists: " + original_hd)
    else:
        print("Creating " + original_hd)
        create_hd_cmd_list = ["VBoxManage", "createhd", "--filename", hd_prefix + ".vdi", "--sizebyte", str(size_byte),
                              "--format", "VDI"]
        create_hd_process = subprocess.run(create_hd_cmd_list, encoding='utf-8')

        print("Removing " + original_hd + " from VirtualBox media registry so UUID can be changed")
        closemedium_cmd_list = ["VBoxManage", "closemedium", "disk", hd_prefix + ".vdi"]
        create_hd_process = subprocess.run(closemedium_cmd_list, encoding='utf-8')

        if create_hd_process.returncode == 0:
            # Update VirtualBox UUID of newly copied in hard drive
            set_uuid_cmd_list = ["VBoxManage", "internalcommands", "sethduuid", original_hd, DRIVE_DICT[hd_prefix]['uuid']]
            subprocess.run(set_uuid_cmd_list, encoding='utf-8')

            print("Backup of " + original_hd + " to " + zeroed_hd)
            shutil.copyfile(original_hd, zeroed_hd)


def create_vm(vm_name, hd_to_attach):
    print("Creating " + vm_name)
    create_vm_cmd_list = ["VBoxManage", "createvm", "--name", vm_name, "--ostype", "Windows10_64", "--register"]
    subprocess.run(create_vm_cmd_list, encoding='utf-8')
    # Add to group
    group_cmd_list = ["VBoxManage", "modifyvm", vm_name,
                      "--groups", "/Rescuezilla.Integration.Suite"]
    subprocess.run(group_cmd_list, encoding='utf-8')

    # Set memory and network
    memory_network_cmd_list = ["VBoxManage", "modifyvm", vm_name,
                               "--ioapic", "on",
                               "--memory", "2048", "--vram", "128",
                               "--nic1", "nat",
                               "--description", "VM created by Rescuezilla's Integration Test Suite script."]
    subprocess.run(memory_network_cmd_list, encoding='utf-8')

    # Add DVD drive
    add_ide_cmd_list = ["VBoxManage", "storagectl", vm_name, "--name", "IDE Controller", "--add", "ide", "--controller",
                        "PIIX4"]
    subprocess.run(add_ide_cmd_list, encoding='utf-8')
    add_dvd_drive_cmd_list = ["VBoxManage", "storageattach", vm_name, "--storagectl", "IDE Controller", "--port", "1",
                              "--device", "0", "--type", "dvddrive", "--medium", "emptydrive"]
    subprocess.run(add_dvd_drive_cmd_list, encoding='utf-8')

    # Add SATA drives
    sata_controller_cmd_list = ["VBoxManage", "storagectl", vm_name, "--name", "SATA Controller", "--add", "sata",
                                "--controller", "IntelAhci"]
    subprocess.run(sata_controller_cmd_list, encoding='utf-8')
    sata_port = 0
    for hd_prefix in MACHINE_DICT[vm_name]['hd_list']:
        if hd_prefix in hd_to_attach:
            attach_storage_cmd_list = ["VBoxManage", "storageattach", vm_name, "--storagectl", "SATA Controller",
                                       "--port",
                                       str(sata_port), "--device", "0", "--type",
                                       "hdd", "--medium", hd_prefix + ".vdi"]
            subprocess.run(attach_storage_cmd_list, encoding='utf-8')
        sata_port += 1

    # Set firmware
    boot_order_cmd_list = ["VBoxManage", "modifyvm", vm_name, "--firmware", MACHINE_DICT[vm_name]['firmware']]
    subprocess.run(boot_order_cmd_list, encoding='utf-8')

    # Configure boot order
    boot_order_cmd_list = ["VBoxManage", "modifyvm", vm_name, "--boot1", "dvd", "--boot2", "disk", "--boot3", "none",
                           "--boot4", "none"]
    subprocess.run(boot_order_cmd_list, encoding='utf-8')

    # Configure a VirtualBox Shared Folder so the VM can read/write to the host machine
    # To mount, within the VM run: mkdir shared; mount -t vboxsf shared shared
    shared_folder_cmd_list = ["VBoxManage", "sharedfolder", "add", vm_name, "--name", "rescuezilla.shared.folder",
                              "--hostpath", HOST_SHARED_FOLDER, "--automount"]
    subprocess.run(shared_folder_cmd_list, encoding='utf-8')

    # Disable VM audio to stop a weird PulseAudio static issue on testing host Linux environment
    disable_audio_cmd_list = ["VBoxManage", "modifyvm", vm_name, "--audio", "none"]
    subprocess.run(disable_audio_cmd_list, encoding='utf-8')

    # Configure first network interface to use host-only adapter
    print("Configure first network interface to use host-only NIC: " + VIRTUAL_BOX_HOSTONLYIFS)
    hostonly_nic_cmd_list = ["VBoxManage", "modifyvm", vm_name, "--nic1", "hostonly", "--hostonlyadapter1",
                             VIRTUAL_BOX_HOSTONLYIFS]
    subprocess.run(hostonly_nic_cmd_list, encoding='utf-8')

    print("Configure DHCP server on " + VIRTUAL_BOX_HOSTONLYIFS + " with a static lease (reserved IP address) of " + MACHINE_DICT[vm_name]['ip'] +
                                                                  " associated with the MAC address of the first "
                                                                  "interface of the VM.")
    reserve_ip_address_cmd_list = ["VBoxManage", "dhcpserver", "modify", "--interface", VIRTUAL_BOX_HOSTONLYIFS, "--vm",
                                   vm_name, "--nic", "1", "--fixed-address", MACHINE_DICT[vm_name]['ip']]
    subprocess.run(reserve_ip_address_cmd_list, encoding='utf-8')


def start_vms(machine_key_list):
    for vm_name in machine_key_list:
        print("Run " + vm_name)
        run_vm_cmd_list = ["VBoxManage", "startvm", vm_name, "--type", "headless"]
        subprocess.run(run_vm_cmd_list, encoding='utf-8')


def _is_shutdown_aborted(vm_name):
    showinfo_vm_cmd_list = ["VBoxManage", "showvminfo", vm_name, "--machinereadable"]
    process = subprocess.run(showinfo_vm_cmd_list, encoding='utf-8', capture_output=True)
    return 'VMState="poweroff"' in process.stdout or 'VMState="aborted"' in process.stdout or process.returncode != 0


def stop_vms(machine_key_list):
    for vm_name in machine_key_list:
        print("Sending ACPI shutdown " + vm_name)
        shutdown_vm_cmd_list = ["VBoxManage", "controlvm", vm_name, "acpipowerbutton"]
        subprocess.run(shutdown_vm_cmd_list, encoding='utf-8')
        has_shutdown = False
        # Number of 1 second ticks waiting for the ACPI shutdown to take effect before hard poweroff.
        timeout_ticks = 60
        print("Sending poweroff in: ", end="")
        sys.stdout.flush()
        while timeout_ticks > 0:
            print(str(timeout_ticks) + " ", end="")
            sys.stdout.flush()
            if _is_shutdown_aborted(vm_name):
                has_shutdown = True
                break
            else:
                timeout_ticks = timeout_ticks - 1
                sleep(1)

        if not has_shutdown:
            print("\nSending poweroff to " + vm_name)
            poweroff_vm_cmd_list = ["VBoxManage", "controlvm", vm_name, "poweroff"]
            subprocess.run(poweroff_vm_cmd_list, encoding='utf-8')


def check_vm(vm_name, contains):
    timeout_ticks = 60
    print("Waiting for VM to confirm successful boot: ", end="")
    while timeout_ticks > 0:
        print(str(timeout_ticks) + " ", end="")
        if _is_shutdown_aborted(vm_name):
            print("\nNot running: " + vm_name)
            return False
        else:
            try:
                print("\nConnecting to: " + vm_name + " on " + MACHINE_DICT[vm_name]['ip'])
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((MACHINE_DICT[vm_name]['ip'], CHECK_SOCKET))
                print("Connected: ", s)

                # Read from socket until EOF
                data = bytearray()
                while True:
                    message = s.recv(100)
                    if not message:
                        break
                    data.extend(message)
                s.close()
                string = data.decode('utf8').strip()

                print("received data: ", string)
                if contains in string:
                    print("Found " + contains + " within received data " + string)
                    return True
                else:
                    print("Did not find " + contains + " within received data " + string)
                    return False
            except (ConnectionRefusedError, OSError, TimeoutError):
                print ("Unable to connect.")
        timeout_ticks = timeout_ticks - 1
        sleep(1)
    return False


def ping_vm(vm_name):
    timeout_ticks = 60
    print("Waiting for VM to reply to ping: ", end="")
    while timeout_ticks > 0:
        print(str(timeout_ticks) + " ", end="")
        if _is_shutdown_aborted(vm_name):
            print("\nNot running: " + vm_name)
            return False
        else:
            print("\nPinging: " + vm_name + " on " + MACHINE_DICT[vm_name]['ip'])
            response = os.system("ping -c 1 -w2 " + MACHINE_DICT[vm_name]['ip'] + " > /dev/null 2>&1")
            # and then check the response...
            if response == 0:
                print("Successfully pinged!")
                return True
        timeout_ticks = timeout_ticks - 1
        sleep(1)
    return False


def insertdvd_vm(vm_name, path_to_dvd):
    abs_path_to_dvd = os.path.abspath(path_to_dvd)
    print("Inserting DVD " + abs_path_to_dvd + " into " + vm_name)
    insert_dvd_cmd_list = ["VBoxManage", "storageattach", vm_name, "--storagectl", "IDE Controller", "--port",
                              "1", "--device", "0", "--type", "dvddrive", "--medium", abs_path_to_dvd]
    subprocess.run(insert_dvd_cmd_list, encoding='utf-8')


def removedvd_vm(vm_name):
    print("Removing DVD from " + vm_name)
    insert_dvd_cmd_list = ["VBoxManage", "storageattach", vm_name, "--storagectl", "IDE Controller", "--port",
                              "1", "--device", "0", "--type", "dvddrive", "--medium", "emptydrive"]
    subprocess.run(insert_dvd_cmd_list, encoding='utf-8')


def _exit(is_success):
    if is_success:
        exit(0)
    else:
        exit(1)


def handle_command(args):
    args_dict = vars(args)
    if 'vm' not in args_dict.keys():
        args.vm = []
    if 'hd' not in args_dict.keys():
        args.hd = []

    if args.vm == "all":
        # If no list of VMs is specified, simply consider all VMs
        machine_key_list = MACHINE_DICT.keys()
        if args.hd == "all":
            # If no list of HDs is specified, simply consider all HDs associated with all VMs
            hd_key_list = DRIVE_DICT.keys()
        else:
            # Otherwise consider the specific HDs given
            hd_key_list = args.hd
    else:
        machine_key_list = args.vm
        if args.hd == "all":
            # If a list of VMs has been specified, carefully gather all hard drives assocated with those machines
            hd_set = set()
            for vm_key in machine_key_list:
                for hd_key in MACHINE_DICT[vm_key]['hd_list']:
                    hd_set.add(hd_key)
            hd_key_list = list(hd_set)
        else:
            hd_key_list = args.hd

    if args.command == "init":
        initialize_vms(hd_key_list, machine_key_list)
    elif args.command == "listvm":
        for vm_key in machine_key_list:
            if set(MACHINE_DICT[vm_key]['hd_list']).intersection(set(hd_key_list)):
                print(vm_key)
    elif args.command == "listhd":
        hd_set = set()
        for vm_key in machine_key_list:
            hd_set.update(set(MACHINE_DICT[vm_key]['hd_list']))
        for hd_key in hd_set:
            print(hd_key)
    elif args.command == "listip":
        for vm_key in machine_key_list:
            print(MACHINE_DICT[vm_key]['ip'])
    elif args.command == "deinit":
        deinitialize_vms(hd_key_list, machine_key_list)
    elif args.command == "reset":
        reset_hd(hd_key_list)
    elif args.command == "deploy":
        deploy_hd(hd_key_list)
    elif args.command == "commit":
        commit_hd(hd_key_list, args.force)
    elif args.command == "start":
        start_vms(machine_key_list)
    elif args.command == "stop":
        stop_vms(machine_key_list)
    elif args.command == "check":
        all_success = True
        for vm_name in machine_key_list:
            all_success = all_success and check_vm(vm_name, args.contains)
        _exit(all_success)
    elif args.command == "ping":
        all_success = True
        for vm_name in machine_key_list:
            all_success = all_success and ping_vm(vm_name)
        _exit(all_success)
    elif args.command == "insertdvd":
        all_success = True
        for vm_name in machine_key_list:
            all_success = all_success and insertdvd_vm(vm_name, args.path_to_dvd)
        _exit(all_success)
    elif args.command == "removedvd":
        all_success = True
        for vm_name in machine_key_list:
            removedvd_vm(vm_name)
        _exit(all_success)
    pass


def main():
    Path(VIRTUAL_BOX_FOLDER).mkdir(parents=True, exist_ok=True)
    os.chdir(VIRTUAL_BOX_FOLDER)

    parser = argparse.ArgumentParser(prog="test_suite.py", description="Rescuezilla's Integration Test Suite")
    subparser = parser.add_subparsers(
        title="Rescuezilla's Integration Test Suite is controlled by a variety of commands:", metavar='command',
        dest="command")

    command_dict = {
        'listvm': {'help': "List VirtualBox VMs",
                 'vm_help': "List specific machine(s)", "hd_help": "Filter to only VMs containing specific drive(s)"},
        'listhd': {'help': "List VirtualBox HDs",
                   'vm_help': "List HDs associated with specific machine(s)"},
        'listip': {'help': "List IP addresses configured for VirtualBox HDs",
                   'vm_help': "List IP addresses associated with specific machine(s)"},
        'init': {
            'help': "Create a large number of VirtualBox VMs and blank drives. Note: this replaces network interface vboxnet0",
            'vm_help': "Initialize specific machine(s)", "hd_help": "Initialize specific drive(s)"},
        'deinit': {'help': "Remove the test suite's VirtualBox VMs and drives created by the 'init' command. Note: this deletes network interface vboxnet0",
                   'vm_help': "Remove specific machine(s)",
                   "hd_help": "Remove specific drive(s)"},
        'reset': {'help': "Overwrite test suite's VirtualBox drives with blank drive",
                  'vm_help': "Resets drives in specific machine(s) (note drives may be shared with other machines)",
                  "hd_help": "Reset a specific drive(s)"},
        'deploy': {'help': "Overwrites test suite's VirtualBox drives with the pre-configured OS VDI images",
                   'vm_help': "Deploy drives in specific machine(s) (note drives may be shared with other machines)",
                   "hd_help": "Deploy a specific drive(s)"},
        'insertdvd': {'help': "Insert a DVD into VirtualBox VM", 'vm_help': "Machine(s) to which insert DVD"},
        'removedvd': {'help': "Remove DVD from VirtualBox VM", 'vm_help': "Machine(s) to remove DVD"},
        'commit': {
            'help': "Replaces the pre-configured OS repository with the contents of the test suite's VirtualBox drives",
            'vm_help': " Replace drives in specific machine (note drives may be shared with other machines)",
            "hd_help": "Replace a specific drive"},
        'start': {'help': "Start VM", 'vm_help': "Start machine(s)"},
        'stop': {'help': "Stop a VirtualBox VM", 'vm_help': "Stop machine(s)"},
        'check': {'help': "Connect to an open port to see if the OS booted as expected, and receives preconfigured string. Requires server installed on machine.", 'vm_help': ""},
        'ping': {'help': "Ping VM to see if the OS booted as expected. Similar to 'check' but doesn't require a configured server. UNlike 'check', cannot distinguish between different operating systems", 'vm_help': ""},

        'run': {'help': "Run end-to-end integration test to test backup, restore and boot",
                'vm_help': "Run test on machine(s)"},
    }

    parser_dict = {}
    for command_key in command_dict.keys():
        parser_dict[command_key] = subparser.add_parser(command_key, help=command_dict[command_key]['help'])
        parser_dict[command_key].set_defaults(func=handle_command)
        if 'vm_help' in command_dict[command_key].keys():
            parser_dict[command_key].add_argument('--vm', nargs='*', help=command_dict[command_key]['vm_help'],
                                                  default="all")
        if 'hd_help' in command_dict[command_key].keys():
            parser_dict[command_key].add_argument('--hd', nargs='*', help=command_dict[command_key]['hd_help'],
                                              default="all")
    parser_dict['commit'].add_argument('--force', help='Confirm overwrite the pre-configured OS VDI image(s)', action='store_true')
    parser_dict['insertdvd'].add_argument('--path-to-dvd', help='DVD to insert', metavar="path_to_dvd", type=str, required=True)
    parser_dict['check'].add_argument('--contains', help='Return success if the provided string is within the received string', metavar="contains", type=str, default="")

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)


if __name__ == "__main__":
    main()
