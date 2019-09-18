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

# Build an immutable docker image from the Dockerfile, labelled with a
# meaningful tag
docker build --tag builder.image .

# Construct a (mutable) docker container from the docker image, give it
# extended privileges (required for the chroot bind mount), label it with a
# meaningful name, execute the application /bin/cat, so the container doesn't
# automatically exit
docker run --rm --detach --privileged --name builder.container -v `pwd`:/home/redobackup -t builder.image cat

# Execute the Makefile's install target within the docker container. This step
# may take some time. Hundreds of megabytes of packages are downloaded from the
# Ubuntu mirror during a build.
docker exec -it builder.container make -C /home/redobackup install 

# Test the generated ISO image in a virtual machine.
```
