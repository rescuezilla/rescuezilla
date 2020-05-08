## Building a bootable ISO image

Note: [You can download the latest Rescuezilla ISO image here](https://github.com/rescuezilla/rescuezilla/releases/latest). This page is intended for developers.
 
### Background

A host system capable of running debootstrap, chroot and bind mounts is required. With such a host system, a bootable ISO image can be generated in a single `make` command.

### Build without docker

Any Debian 10, Ubuntu 18.04, or derivative such as Linux Mint should be able to run the following:
```bash
sudo apt-get update
# The AMD64 version of Rescuezilla is based on Ubuntu 20.04 Focal, so you may find you need a more
# recent version of debootstrap (from the backports repository) to bootstrap a Focal environment.
sudo apt-get install git-lfs git make rsync sudo debootstrap isolinux syslinux syslinux-utils \
                     squashfs-tools genisoimage gettext
git lfs clone https://github.com/rescuezilla/rescuezilla
cd rescuezilla/
# sudo privileges required for the chroot bind mount
sudo make

# Test the generated ISO image in a virtual machine.
sudo apt-get install virtualbox
```

### Build with docker

An optional Dockerfile is provided to generate a consistent build environment on a much larger variety of operating systems. The Dockerfile is managed under version-control just like the source code, which means the ideal build environment is always available, even when building very old commits. Official releases are built using this approach. See .travis.yml for docker build instructions.

To be used effectively in development, Docker has a relatively steep learning curve. If you prefer to avoid docker entirely, stick to the 'Build without docker' instructions.

### Suggested developer workflow

The build script caches the debootstrap packages, apt-get packages and apt-get indexes. The first build may download hundreds of megabytes of deb packages, but subsequent builds don't need to download the same files again. Even with cached deb packages, doing a from-scratch extract and install of deb files still takes minutes (even on modern computers).

While contributions to Rescuezilla frontend applications can be done without building an ISO image, for many contributions, the most efficient way for the typical developer will be to first build an ISO image using the standard instructions (above), then boot the ISO image in a [virtual machine](https://github.com/rescuezilla/rescuezilla/wiki/Constructing-Rescuezilla-VirtualBox-Test-Environment), and make any proposed changes inside its (non-persistent) filesystem. Once satisfied of a proposed change, any files that have been modified can be exported from the virtual machine (using say, `scp`), and committed into codebase. When all changes have been committed, use the build scripts to generate a new ISO image, and test/debug until satisfied.

The most efficient workflow really depends on the feature you are trying to add. If comfortable, an alternative development workflow may be making changes inside an interactive chroot environment, and when ready to test, compress the chroot directory into a new squashfs root filesystem and make a new ISO9660 image, then boot the ISO image in a virtual machine to test/debug the change, as usual. You may wish to [construct a VirtualBox environment](https://github.com/rescuezilla/rescuezilla/wiki/Constructing-Rescuezilla-VirtualBox-Test-Environment) for a convenient sandbox for testing ISO images.

To non-developers: [You can download the latest Rescuezilla ISO image here](https://github.com/rescuezilla/rescuezilla/releases/latest). This page is intended for developers.
