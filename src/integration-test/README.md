# Rescuezilla's Integration Test Suite

## Background

Rescuezilla is a Python application with unit tests. These can be run using `make test`. Whilst unit tests are definitely useful, they are not a substitute for testing every Rescuezilla version with an end-to-end integration test suite to automatically test the project against (eventually thousands of) test images and configurations.

Here are some key [design considerations](https://github.com/rescuezilla/rescuezilla/issues/151):

* Rescuezilla needs to work on multiple CPU architectures: AMD64, i386, ARM64, etc
     * Assuming there are build bots so each architecture can run natively, rather than through slow Qemu emulation.
* Rescuezilla needs to have ISO images based on many Debian-based distros
     * Ubuntu LTS, Ubuntu latest, Debian LTS and Debian Sid
* Rescuezilla needs to have packages available for many other Linux distributions
     * Arch-based, RedHat-based, etc

## How It Works

Rescuezilla's integration test suite is itself a Python application (integration_test.py) that manages VirtualBox VMs.

The test suite is able to add, remove, start and stop a number of virtual machines (attaching and detaching virtual hard drives, configuring each VM with a static DHCP lease).

The primary virtual machine boots a Rescuezilla environment. This can be a custom ISO image, or any Linux distribution installed on a virtual hard drive. The only requirement is the environment needs an SSH server configured (with SSH keys) so that the test script can execute Rescuezilla within the VM using its command-line interface.

The test suite can then restore a large number of backup images (specified by configuration files).

The test suite then checks whether the subsequently restored image can boot by launching the VM. Once the target VM has booted, the restored operating system has been pre-configured to automatically listen on a TCP network port so that the test suite can connect to it and receive a short message indicating that the boot (and therefore the restore) was successful.

## Preparing Rescuezilla ISO image

Public Rescuezilla ISO images keeps the number of services, ports and installed programs to an absolute minimum. However, for the integration tests the script needs to connect to the Rescuezilla environment (over SSH), and also needs to be able to query that a particular operating system (including Rescuezilla ISO itself) has successfully booted. This is achieved by configuring each OS disk with a simple TCP query server (connect on TCP port 9999 and receive an informational string message).

For the Rescuezilla ISO, the SSH server and query server can be enabled by building the ISO with the integration test variable enabled:

```
# Authorize your host system's SSH key
mkdir 700 src/livecd/chroot/home/ubuntu/.ssh/
cp ~/.ssh/id_rsa.pub src/livecd/chroot/home/ubuntu/.ssh/authorized_keys
# Build Rescuezilla ISO image with an SSH server, and the TCP query server
IS_INTEGRATION_TEST=true make 
```

For Rescuezilla's test operating system VDI files and image repository files (see below), configuring the TCP query server was done by manually running the installer scripts.

## Preprepared disk images

**As of writing, the Rescuezilla operating system VDI files, and image repository has not yet been publicly released.** Constructing such an image repository is extremely time consuming (involving installing many different operating systems and making backups with many different tools), so this repository will eventually be made available for anybody interested in contributing to Rescuezilla and Clonezilla.

Each OS is simply a standard OS install, plus the Rescuezilla Integration Test TCP query server that's configured as an auto-restarting service (see: scripts/ folder for the installers: install_linux_query_tcp_server.sh and install_windows_query_tcp_server.bat).

## Usage

A brief description of the usage is presented below. It may be out of date, so please check with `integration_test.py --help`.

./integration_test.py listvm  [--vm vm_name] [--hd hd_name]
    Lists the VirtualBox VMs that are configured (but potentially not-yet initialized) 

./integration_test.py listhd  [--hd hd_name]
    Lists the virtual drives that are configured (but potentially not-yet initialized) 

./integration_test.py init [--vm vm_name] [--hd hd_name]
    Create a large number of VirtualBox VMs and virtual drives. The hard drives are dynamically allocated so this step doesn't use much disk space.

./integration_test.py deinit  [--vm vm_name] [--hd hd_name]
    Delete the VMs and virtual drives created by the 'init' command

./integration_test.py reset [--vm vm_name] [--hd hd_name]
    Replaces the virtual drive with a zeroed version

./integration_test.py deploy [--vm vm_name] [--hd hd_name]
    Copy in preprepared disk images. See "Preprepared disk images" section.

./integration_test.py commit [--vm vm_name] [--hd hd_name] [--force]
    Backup the VM hard drives to be the new set of preprepared disk images for use with "deploy"

./integration_test.py start [--vm vm_name]
    Start the specified VM(s)

./integration_test.py stop  [--vm vm_name]
    Stop the specified VM(s)

./integration_test.py check [--vm vm_name] [--contains expected_string]
    Check VM(s) have booted by trying to connect on a specific TCP port, and returns success if the received data contains expected_string (default: empty string).

## Example

See the test case scripts (in the tests/ folder) to see clear examples on how to use the integration test Python application.
