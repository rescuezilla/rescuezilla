# Typically, constructing a Linux live image relies on files from the host system. This Dockerfile,
# a version-controlled mechanism to produce a host system for live image builds.

# Note: the host system Ubuntu version (below) is defined separately from the version of the
# generated Ubuntu image.
ARG CODENAME=noble
FROM ubuntu:${CODENAME}
# Define the Ubuntu code name again because Docker clears the argument after the FROM command.
ARG CODENAME=noble

# Ensure all Dockerfile package installation operations are non-interactive, DEBIAN_FRONTEND=noninteractive is insufficient [1]
# [1] https://github.com/phusion/baseimage-docker/issues/58
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Refresh the apt package metadata
RUN apt-get update

RUN apt-get install --yes \
                          # Install required dependencies for the build
                          make rsync sudo debootstrap squashfs-tools xorriso memtest86+ git git-lfs gettext \
                          dosfstools mtools checkinstall cmake time \
                          shim-signed grub-efi-amd64-signed grub-efi-amd64-bin grub-efi-ia32-bin grub-pc-bin \
                          devscripts debhelper ccache \
                          # Dependencies for "sfdisk" and "partclone.restore" build.
                          libtool-bin gawk pkg-config comerr-dev docbook-xsl e2fslibs-dev fuse3 \
                          libaal-dev libblkid-dev libbsd-dev libext2fs-dev libncurses5-dev \
                          libncursesw5-dev libreadline-dev libreadline8 \
                          libreiser4-dev libtinfo-dev libxslt1.1 nilfs-tools ntfs-3g ntfs-3g-dev \
                          quilt sgml-base uuid-dev vmfs-tools xfslibs-dev xfsprogs xml-core \
                          xsltproc libssl-dev \
                          # Select runtime dependencies required for running the unit tests
                          python3-gi libgtk-3-dev python3-whichcraft python3-babel \
                          # Install optional dependencies for quality-of-life when debugging
                          tmux vim

# Restore interactivity of package installation within Docker
RUN echo 'debconf debconf/frontend select Dialog' | debconf-set-selections
