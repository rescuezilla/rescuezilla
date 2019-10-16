## Building a bootable ISO image

### Background

A host system capable of running debootstrap, chroot and bind mounts is required. With such a host system, a bootable ISO image can be generated in a single `make install` command.

To help automate the build across a variety of operating systems, a Dockerfile has been provided. This Dockerfile is used to generate an Ubuntu docker container which may act as the "host system". To be used effectively in development, Docker has a relatively steep learning curve, if you prefer to avoid docker entirely, the `make install` should work without issue on a native Ubuntu installation, or in a Ubuntu virtual machine.

### Build instructions using Docker

Suggested dependencies: git, git LFS, Docker (on Debian: https://docs.docker.com/install/linux/docker-ce/debian/)

In a terminal, run the following:
```bash
git clone https://github.com/redobackup/redobackup
cd redobackup/

docker build --tag builder.image .
docker run --rm --detach --privileged --name builder.container -v `pwd`:/home/redobackup -t builder.image cat
docker exec -it builder.container make -C /home/redobackup install 

# Test the generated ISO image in a virtual machine.
```

### Suggested developer workflow

The build script caches the debootstrap packages, apt-get packages and apt-get indexes. The first build may download hundreds of megabytes of deb packages, but subsequent builds don't need to download the same files again. Even with cached deb packages, doing a from-scratch extract and install of deb files still takes minutes (even on modern computers).

For many contributions, the most efficient way for the typical developer will be to first build an ISO image using the standard instructions (above), then boot the ISO image in a virtual machine, and make any proposed changes inside its (non-persistent) filesystem. Once satisfied of a proposed change, any files that have been modified can be exported from the virtual machine (using say, `scp`), and committed into codebase. When all changes have been committed, use the build scripts to generate a new ISO image, and test/debug until satisfied.

If comfortable, an alternative (faster) development workflow is to make changes inside an interactive chroot environment, and when ready to test, compress the chroot directory into a new squashfs root filesystem and make a new ISO9660 image, then boot the ISO image in a virtual machine to test/debug the change, as usual.
