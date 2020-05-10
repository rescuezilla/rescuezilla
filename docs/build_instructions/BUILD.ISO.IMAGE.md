## Building a bootable ISO image

Note: [You can download the latest Rescuezilla ISO image here](https://github.com/rescuezilla/rescuezilla/releases/latest). This page is intended for developers.
 
### Background

An Ubuntu 18.04, or similar Ubuntu-package environment capable of running debootstrap, chroot and bind mounts is currently required. A single `make` command can generate an AMD64 ISO image and an i386 image, which are capable of booting from USB sticks, CD, DVD and any EFI firmware, including with EFI Secure Boot switched on.

Unfortunately, building on Debian and other non Ubuntu-package environments will not work properly, as Debian's package repositories contain different versions of key packages which happen to only trust Debian certificates, namely the Debian-signed GRUB bootloader (`grub-efi-amd64-signed`) which is launched by the Microsoft-signed EFI shim (`shim-signed`). This means that when Secure Boot is enabled, an EFI boot will fail to authenticate Rescuezilla's Canonical-signed kernel images leaving the developer in GRUB Rescue Mode. Fortunately, developers who use any distribution which does not use Canonical's Ubuntu packages (such as Debian) are able to easily construct the ideal Ubuntu-based build environment by following the "Build _with_ docker" instructions on this page. The requirement for a build environment containing Canonical's Ubuntu packages will be removed with task [#59](https://github.com/rescuezilla/rescuezilla/issues/59).

### Build without docker

The following instructions should work on Ubuntu or Ubuntu-derived distributions, but are _not_ recommended on Debian or Debian-derived environments (see above):

```bash
sudo apt-get update
# The AMD64 version of Rescuezilla is based on Ubuntu 20.04 Focal, so you may find you need a more
# recent version of debootstrap (from the backports repository) to bootstrap a Focal environment.
sudo apt-get install git-lfs git make sudo \
                     rsync debootstrap gettext squashfs-tools dosfstools mtools xorriso \
                     # GRUB bootloader and support modules for booting both MBR and EFI boot
                     # across CPU architectures. Notably the AMD64 image *legacy boot* uses
                     # the same 32-bit bootloader as the i386 image.
                     grub-efi-amd64-bin grub-efi-ia32-bin grub-pc-bin \
                     # For Secure Boot, the GRUB binaries need to trust Canonical
                     # signatures, not Debian signatures, as GRUB needs to verify the
                     # Canonical-signed Linux kernel (see "Background" section above).
                     shim-signed grub-efi-amd64-signed

git lfs clone https://github.com/rescuezilla/rescuezilla
cd rescuezilla/
# sudo privileges required for the chroot bind mount
sudo make amd64 i386

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
