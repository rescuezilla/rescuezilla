## Building a bootable ISO image

Note: [You can download the latest Rescuezilla ISO image here](https://github.com/rescuezilla/rescuezilla/releases/latest).  This page is intended for developers.
For Debian/Ubuntu/Linux Mint users there is also a [standalone deb package](https://github.com/rescuezilla/rescuezilla/wiki/Installing-Rescuezilla-from-the-standalone-deb-package).
 
### Build without docker

A single `make deb` command generates a Rescuezilla package ready for installation. (You can also [download](https://github.com/rescuezilla/rescuezilla/wiki/Installing-Rescuezilla-from-the-standalone-deb-package) a standalone deb package of the latest release)

Alternatively, a single `make all` command can generate an AMD64 ISO image and an i386 image, which are complete Ubuntu-based Linux live environments capable of booting from USB sticks, CD, DVD and any EFI firmware, including with EFI Secure Boot switched on.

To construct such an ISO image, an Ubuntu 18.04, or similar Ubuntu-package environment capable of running debootstrap, chroot and bind mounts is currently required. It's currently recommended _only_ Ubuntu environments be used to build the ISO image as Debian and other non-Canonical package environments GRUB packages are signed differently (see the "EFI Secure Boot" section below). To build on environments other than Ubuntu 18.04, see the "Build ISO with docker" section below.

```bash
# Please note: the following instructions are based on the Dockerfile and the .travis.yml file, which gets frequently
# executed by Rescuezilla's TravisCI build bot automatically so is contantly being tested. The exact instructions below
# sometimes gets out-of-date, especially if your build environment is based on a different version of Debian or Ubuntu.

sudo apt-get update
sudo apt-get install git-lfs git make sudo \
                     rsync debootstrap gettext squashfs-tools dosfstools mtools xorriso \
                     memtest86+ devscripts debhelper checkinstall cmake \
                     grub-efi-amd64-bin grub-efi-ia32-bin grub-pc-bin \
                     shim-signed grub-efi-amd64-signed \
                     libtool-bin gawk pkg-config comerr-dev docbook-xsl e2fslibs-dev fuse \
                     libaal-dev libblkid-dev libbsd-dev libext2fs-dev libncurses5-dev \
                     libncursesw5-dev libntfs-3g883 libreadline-gplv2-dev libreadline5 \
                     libreiser4-dev libtinfo-dev libxslt1.1 nilfs-tools ntfs-3g ntfs-3g-dev \
                     quilt sgml-base uuid-dev vmfs-tools xfslibs-dev xfsprogs xml-core \
                     xsltproc ccache

git lfs clone https://github.com/rescuezilla/rescuezilla
cd rescuezilla/
git submodule init
# Download 'partclone' and 'util-linux' submodules
git submodule update --recursive

# Optional: Build only the standalone deb packages without bothering with the live environment
make deb

## Optional : set the configure_mirrors.sh file as executable
chmod +x configure_mirror.sh
# run the file - this will isntall netselect and should configure Ubuntu mirrors to be the fastest and closest to you
sudo ./configure_mirror.sh

# Optional: Move build environment to RAMDISK for increased build perfomance
# This process is manual as not everyone will want to do this.
# First check that your build system has a minimum of 8Gb available ram then
# Make sure you remember to clean the environment copy and ISO produced
# and move everything back to disk when you are done.
sudo mount -t tmpfs -o rw,size=7G tmpfs /mnt/ramdisk/

# Next rsync the working rescuezilla directories into the ramdisk
# Adjust paths as needed
rsync -av /home/*USER*/rescuezilla /mnt/ramdisk/
# cd /mnt/ramdisk/rescuezilla and work from there.

# Build the amd64 ISO image based on Ubuntu 20.04 (Focal), and the deb files.
# This should work on Ubuntu or Ubuntu-derived distributions, but is _not_ recommended
# Debian or Debian-derived environments (see "EFI Secure Boot" section below).
#
# sudo privileges required for the chroot bind mount
sudo make focal

# Test the generated ISO image in a virtual machine. (see suggested workflow section below)
sudo apt-get install virtualbox
```

### Build ISO with docker

An optional Dockerfile is provided to generate a consistent build environment on a much larger variety of operating systems. The Dockerfile is managed under version-control just like the source code, which means the ideal build environment is always available, even when building very old commits. Official releases are built using this approach. See .travis.yml for docker build instructions.

To be used effectively in development, Docker has a relatively steep learning curve. If you prefer to avoid docker entirely, stick to the 'Build without docker' instructions.

### EFI Secure Boot on Debian and non-Canonical package environments

Rescuezilla ISO image provides an Ubuntu-based live environment, so for Secure Boot to work the ISO image build environment currently needs the host system to contain a Canonical Ubuntu package environment. Debian and other non Ubuntu-package environments will _not_ construct an ISO image that boots with Secure Boot, because Debian's package repositories contain different versions of key bootloader packages which happen to only trust Debian certificates, namely the Debian-signed GRUB bootloader (`grub-efi-amd64-signed`) which is launched by the Microsoft-signed EFI shim (`shim-signed`). This means that when Secure Boot is enabled, an EFI boot will fail to authenticate Rescuezilla's Canonical-signed kernel images leaving the developer in GRUB Rescue Mode. The "Build _with_ docker" instructions on this page provides developers who use any distribution which does not use Canonical's Ubuntu packages (such as Debian) a pathway to generating an image that works with Secure Boot by first constructing the ideal Ubuntu-based build environment. The requirement for a host machine package environment to contain Canonical's Ubuntu packages will be removed with task [#59](https://github.com/rescuezilla/rescuezilla/issues/59).

### Suggested developer workflow

The build script caches the debootstrap packages, apt-get packages and apt-get indexes. The first build may download hundreds of megabytes of deb packages, but subsequent builds don't need to download the same files again. Even with cached deb packages, doing a from-scratch extract and install of deb files still takes minutes (even on modern computers).

Contributions to Rescuezilla frontend applications can of course be done without building an ISO image at all: the most efficient way is to just build the deb package with `make deb`. For many other contributions, the typical developer may prefer to first build an ISO image using the standard instructions (above), then boot the ISO image in a [virtual machine](https://github.com/rescuezilla/rescuezilla/wiki/Constructing-Rescuezilla-VirtualBox-Test-Environment), and then make any proposed changes inside its (non-persistent) filesystem. Once satisfied of a proposed change, any files that have been modified can be exported from the virtual machine (using say, `scp`), and committed into codebase. When all changes have been committed, use the build scripts to generate a new ISO image, and test/debug until satisfied.

The most efficient workflow really depends on the feature you are trying to add. You may wish to [construct a VirtualBox environment](https://github.com/rescuezilla/rescuezilla/wiki/Constructing-Rescuezilla-VirtualBox-Test-Environment) for a convenient sandbox for testing ISO images.

To non-developers: [You can download the latest Rescuezilla ISO image here](https://github.com/rescuezilla/rescuezilla/releases/latest). This page is intended for developers.
