# Typically, constructing a Linux live image relies on files from the host system. This Dockerfile,
# a version-controlled mechanism to produce a host system for live image builds.

# Note: the host system Ubuntu version (below) is defined separately from the version of the
# generated Ubuntu image.
ARG CODENAME=noble
FROM ubuntu:${CODENAME}
# Define the Ubuntu code name again because Docker clears the argument after the FROM command.
ARG CODENAME=noble

# Detect the running container architecture (can be overridden via --build-arg)
ARG RUNNING_CONTAINER_ARCH
RUN RUNNING_CONTAINER_ARCH="${RUNNING_CONTAINER_ARCH:-$(dpkg --print-architecture)}"

# Copy the apt repository mirror list into the Docker image.
# 
# For increased transfer rates, consider selecting a mirror geographically
# closer mirror.
# 
# Note: After the support window for a specific release ends, the packages are
# moved to the 'old-releases' URL, which makes substitution becomes mandatory
# in-order to build older releases from scratch.
#
RUN echo $CODENAME
COPY src/livecd/chroot/etc/apt/sources.list /etc/apt/sources.list
# Copy the apt-preferences file to ensure backports and proposed repositories are never automatically selected.
COPY "src/livecd/chroot/etc/apt/preferences.d/89_CODENAME_SUBSTITUTE-backports_default" "/etc/apt/preferences.d/89_$CODENAME-backports_default"
COPY "src/livecd/chroot/etc/apt/preferences.d/90_CODENAME_SUBSTITUTE-proposed_default" "/etc/apt/preferences.d/90_$CODENAME-proposed_default"

RUN RUNNING_CONTAINER_ARCH="${RUNNING_CONTAINER_ARCH:-$(dpkg --print-architecture)}" \
; if [ "$RUNNING_CONTAINER_ARCH" = "amd64" ] || [ "$RUNNING_CONTAINER_ARCH" = "i386" ]; then \
    URL="http://archive.ubuntu.com/ubuntu" \
    ; sed --in-place "s*URL_SUBSTITUTE*$URL*g" "/etc/apt/sources.list" \
; else \
    URL="http://ports.ubuntu.com/ubuntu-ports/ubuntu-ports" \
    ; sed --in-place "s*URL_SUBSTITUTE*$URL*g" "/etc/apt/sources.list" \
; fi


RUN sed --in-place "s*CODENAME_SUBSTITUTE*$CODENAME*g" "/etc/apt/sources.list"
RUN cat /etc/apt/sources.list
RUN sed --in-place "s*CODENAME_SUBSTITUTE*$CODENAME*g" /etc/apt/preferences.d/89_${CODENAME}-backports_default
RUN sed --in-place "s*CODENAME_SUBSTITUTE*$CODENAME*g" /etc/apt/preferences.d/90_${CODENAME}-proposed_default

# Ensure all Dockerfile package installation operations are non-interactive, DEBIAN_FRONTEND=noninteractive is insufficient [1]
# [1] https://github.com/phusion/baseimage-docker/issues/58
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Refresh the apt package metadata
RUN apt-get update

RUN apt-get install --yes \
                          # Install required dependencies for the build
                          make rsync sudo debootstrap squashfs-tools xorriso \
                          git git-lfs gettext \
                          dosfstools mtools checkinstall cmake time \
                          shim-signed \
                          devscripts debhelper ccache \
                          # Dependencies for "sfdisk" and "partclone.restore" build.
                          libtool-bin gawk pkg-config comerr-dev docbook-xsl e2fslibs-dev fuse3 \
                          libaal-dev libblkid-dev libbsd-dev libext2fs-dev libncurses5-dev \
                          libncursesw5-dev libreadline-dev libreadline8 \
                          libreiser4-dev libtinfo-dev libxslt1.1 nilfs-tools ntfs-3g ntfs-3g-dev \
                          quilt sgml-base uuid-dev vmfs-tools xfslibs-dev xfsprogs xml-core \
                          xsltproc libssl-dev libxxhash-dev \
                          # Select runtime dependencies required for running the unit tests
                          python3-gi libgtk-3-dev python3-whichcraft python3-babel \
                          # Needed to install Astral's Python tooling
                          curl \
                          # Install optional dependencies for quality-of-life when debugging
                          tmux vim

# Install key packages that are only available for containers built on amd64.
RUN RUNNING_CONTAINER_ARCH="${RUNNING_CONTAINER_ARCH:-$(dpkg --print-architecture)}" \
; if [ "$RUNNING_CONTAINER_ARCH" = "amd64" ]; then \
    apt-get install --yes \
        memtest86+ \
        grub-efi-amd64-signed grub-efi-amd64-bin grub-efi-ia32-bin grub-pc-bin \
; fi

# Install key packages that are only available for containers built on arm64.
RUN RUNNING_CONTAINER_ARCH="${RUNNING_CONTAINER_ARCH:-$(dpkg --print-architecture)}" \
; if [ "$RUNNING_CONTAINER_ARCH" = "arm64" ]; then \
    apt-get install --yes \
        grub-efi-arm64 grub-efi-arm64-bin \
; fi

# Install Astral's Python tooling, as on Ubuntu Noble it's not available in the default package repositories.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN . $HOME/.local/bin/env && uv tool install ruff@latest

# Restore interactivity of package installation within Docker
RUN echo 'debconf debconf/frontend select Dialog' | debconf-set-selections
