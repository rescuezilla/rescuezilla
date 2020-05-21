.DEFAULT_GOAL := amd64
.PHONY: all amd64 i386 deb clean-build-dir clean clean-all

all: amd64 i386

buildscripts = build.sh chroot.steps.part.1.sh chroot.steps.part.2.sh

amd64: ARCH=amd64
amd64: CODENAME=focal
export ARCH CODENAME
amd64: deb $(buildscripts)
	./build.sh

i386: ARCH=i386
i386: CODENAME=bionic
export ARCH CODENAME
i386: deb $(buildscripts)
	./build.sh

deb: BASE_BUILD_DIR=$(shell pwd)/build/deb/
deb:
	cd src/apps/rescuezilla/ && BUILD_DIR=$(BASE_BUILD_DIR) $(MAKE) && mv $(BASE_BUILD_DIR)/rescuezilla_*.deb  $(BASE_BUILD_DIR)/../
	# The "drivereset" frontend is currently not maintained and is
	# de-emphasized until a complete overhaul in future
	cd src/apps/drivereset/ && BUILD_DIR=$(BASE_BUILD_DIR) $(MAKE) && mv $(BASE_BUILD_DIR)/drivereset_*.deb  $(BASE_BUILD_DIR)/../
	cd src/apps/graphical-shutdown/ && BUILD_DIR=$(BASE_BUILD_DIR) $(MAKE) && mv $(BASE_BUILD_DIR)/graphical-shutdown_*.deb  $(BASE_BUILD_DIR)/../

clean-build-dir:
	$(info * Unmounting chroot bind mounts)
	for dir in build/*; do \
          umount $$dir/chroot/dev/pts || true ; \
          umount $$dir/chroot/dev/    || true ; \
          umount $$dir/chroot/proc/   || true ; \
          umount $$dir/chroot/sys/    || true ; \
        done
	$(info * Deleting build/ directory)
	rm -rf build/

 
clean: clean-build-dir
	$(info )
	$(info * Deleting cached apt-get indexes, but KEEPING cached deb packages.)
	$(info * This forces an `apt-get update` next build. The cached deb packages)
	$(info * remain so only new packages will need to be downloaded.)
	rm -rf pkg.cache/var.lib.apt.lists.*

clean-all: clean-build-dir
	$(info )
	$(info * Deleting cached apt-get indexes AND cached deb packages)
	rm -rf pkg.cache/
