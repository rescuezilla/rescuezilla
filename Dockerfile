# Typically, constructing a Linux live image relies on files from the host system. This Dockerfile,
# a version-controlled mechanism to produce a host system for live image builds.

# Note: the host system Ubuntu version (below) is defined separately from the version of the
# generated Ubuntu image.
FROM ubuntu:12.04

## Uncomment to substitute a different apt repository. Selecting a mirror geographically closer mirror may
## increase network transfer rates.
##
## Note: After the support window for a specific release ends, the packages are moved to the 'old-releases'
## URL [1], which makes substitution becomes mandatory in-order to build older releases from scratch.
##
## [1] http://old-releases.ubuntu.com/ubuntu
ARG DEFAULT_APT_REPOSITORY_URL=http://archive.ubuntu.com/ubuntu
ARG REPLACEMENT_APT_REPOSITORY_URL=http://old-releases.ubuntu.com/ubuntu
RUN sed --in-place "s*${DEFAULT_APT_REPOSITORY_URL}*${REPLACEMENT_APT_REPOSITORY_URL}*g" /etc/apt/sources.list

# Ensure all Dockerfile package installation operations are non-interactive, DEBIAN_FRONTEND=noninteractive is insufficient [1]
# [1] https://github.com/phusion/baseimage-docker/issues/58
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Refresh the apt package metadata
RUN apt-get update

# Install required dependencies for the build
RUN apt-get install --yes make rsync sudo

# Install optional dependencies for quality-of-life when debugging
RUN apt-get install --yes tmux vim

# Restore interactivity of package installation within Docker
RUN echo 'debconf debconf/frontend select Dialog' | debconf-set-selections

