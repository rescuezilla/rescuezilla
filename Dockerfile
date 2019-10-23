# Typically, constructing a Linux live image relies on files from the host system. This Dockerfile,
# a version-controlled mechanism to produce a host system for live image builds.

# Note: the host system Ubuntu version (below) is defined separately from the version of the
# generated Ubuntu image.
FROM ubuntu:18.04

# Copy the apt repository mirror list into the Docker image.
# 
# For increased transfer rates, consider selecting a mirror geographically
# closer mirror.
# 
# Note: After the support window for a specific release ends, the packages are
# moved to the 'old-releases' URL, which makes substitution becomes mandatory
# in-order to build older releases from scratch.
#
COPY src/livecd/chroot/etc/apt/sources.list /etc/apt/sources.list

# Ensure all Dockerfile package installation operations are non-interactive, DEBIAN_FRONTEND=noninteractive is insufficient [1]
# [1] https://github.com/phusion/baseimage-docker/issues/58
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Refresh the apt package metadata
RUN apt-get update

RUN apt-get install --yes \
                          # Install required dependencies for the build
                          make rsync sudo debootstrap isolinux syslinux squashfs-tools genisoimage memtest86+ git gettext \
                          # Install optional dependencies for quality-of-life when debugging
                          tmux vim

# Restore interactivity of package installation within Docker
RUN echo 'debconf debconf/frontend select Dialog' | debconf-set-selections
