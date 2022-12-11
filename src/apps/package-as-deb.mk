.PHONY: all embed-version deb install
# Makefile to create deb packages for Rescuezilla app suite.
#
# From another Makefile, set the below variables then include this file and call a target.
DEB_BUILD_DIR?=build
# Absolute path for cleaner script
ABS_BUILD_PATH=$(abspath $(DEB_BUILD_DIR))
APP_NAME?=NO_APP_NAME_SET

# TODO: When GNU Make 4.2 becomes available in build environment, use $(.SHELLSTATUS) [1]
# TODO: to check the exit codes of the below shell commands, so improve resilience of this Makefile.
# [1] https://stackoverflow.com/a/40710111

# Get the most recent git tag of a versioned release (deb files don't support git SHA's, so need to abbreviate)
#
# Note: the --match is a glob, not a regex.
LAST_TAGGED_VERSION=$(shell git describe --tags  --match="[0-9].[0-9]*" --abbrev=0)
# Full git version to embed
# If the current commit is not tagged, the version number from `git
# describe --tags  --match="[0-9].[0-9].[0-9]" --dirty` is X.Y.Z-abc-gGITSHA-dirty,
# where X.Y.Z is the previous versioned tag, 'abc' is the number of commits since that tag, gGITSHA is the git sha
# prepended by a 'g', and -dirty is present if the working tree has been modified.
#
# Note: the --match is a glob, not a regex.
VERSION_STRING=$(shell git describe --tags --match="[0-9].[0-9]*" --dirty)
# Date of current git commit in colon-less ISO 8601 format (2013-04-01T130102)
GIT_COMMIT_DATE=$(shell date +"%Y-%m-%dT%H%M%S" --date=@$(shell git show --no-patch --format=%ct HEAD))

WORKING_DIR=$(abspath $(DEB_BUILD_DIR)/build_script_modified_source)
PACKING_DIR=$(abspath $(DEB_BUILD_DIR)/$(APP_NAME)-$(LAST_TAGGED_VERSION))

all:	embed-version deb

# To avoid polluting the source tree with modifications, first copy to a working directory
copy: clean
	mkdir --parents $(WORKING_DIR) || true
	cp --archive ./debian ./$(APP_NAME) $(WORKING_DIR)/
	# Copy this Makefile into the working directory
	cp --archive ../common.app.mk $(WORKING_DIR)/$(APP_NAME)/Makefile

embed-version: copy
	# Substitute version into file
	sed --in-place 's/VERSION-SUBSTITUTED-BY-BUILD-SCRIPT/$(VERSION_STRING)/g' "$(WORKING_DIR)/$(APP_NAME)/usr/share/$(APP_NAME)/VERSION"
	# Substitute git commit date
	sed --in-place 's/GIT-COMMIT-DATE-SUBSTITUTED-BY-BUILD-SCRIPT/${GIT_COMMIT_DATE}/g' "$(WORKING_DIR)/$(APP_NAME)/usr/share/$(APP_NAME)/GIT_COMMIT_DATE"

# Creates a deb file from the application source code, and Debian-specific configuration. It's a bit
# complex since the debian helper executables expect source code tarballs, so much of the below
# is packing and unpackaging source code.
# TODO: Simplify if possible.
deb:
	mkdir --parents $(PACKING_DIR) || true
	$(info * Create gzipped tar archive of Rescuezilla frontend app source code.)
	cd $(WORKING_DIR)/$(APP_NAME) && tar -czf $(ABS_BUILD_PATH)/$(APP_NAME)_$(LAST_TAGGED_VERSION).orig.tar.gz ./
	$(info * Create gzipped tar archive of debian-specific configuration directory.)
	cd $(WORKING_DIR)/ && tar -czf $(ABS_BUILD_PATH)/$(APP_NAME)_$(LAST_TAGGED_VERSION).debian.tar.gz ./debian/
	$(info * Extract $(APP_NAME) source tarball. This makes a copy of the source tree in the build directory)
	cd $(PACKING_DIR) && tar -xzf $(ABS_BUILD_PATH)/$(APP_NAME)_$(LAST_TAGGED_VERSION).orig.tar.gz 
	# Make a copy of the source debian-specific configuration in the build directory
	$(info * Extract debian-specific configuration tarball. This makes a copy of the debian-specific configuration in the build directory)
	cd $(PACKING_DIR) && tar -xzf $(ABS_BUILD_PATH)/$(APP_NAME)_$(LAST_TAGGED_VERSION).debian.tar.gz 
	# The dpkg-buildpackage call construct a "debian" and "orig" tarballs,
	# then extracts the tarball into the build directory. Then command then
	# operates on that copy of the source code: itself running a make
	# invocation on this Makefile (which runs the msgfmt target modifying
	# what is the build tree), then dpkg-buildpackage finishes by creates a
	# deb file.
	# Taking care to pass in environment variable for the Makefile invocation
	$(info * Make deb package by, among other things, running make on a copy of this very Makefile)
	cd $(PACKING_DIR) && APP_NAME=$(APP_NAME) dpkg-buildpackage -b -us -uc

clean: 
	rm -rf $(ABS_BUILD_PATH)
