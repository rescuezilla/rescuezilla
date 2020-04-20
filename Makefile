.DEFAULT_GOAL := i386
.PHONY: all amd64 i386 clean-build-dir clean clean-all

all: amd64 i386

buildscripts = build.sh chroot.steps.part.1.sh chroot.steps.part.2.sh

amd64: ARCH=amd64 CODENAME=bionic
amd64: $(buildscripts)
	CODENAME=$(CODENAME) ARCH=$(ARCH) ./build.sh

i386: ARCH=i386 CODENAME=bionic
i386: $(buildscripts)
	CODENAME=$(CODENAME) ARCH=$(ARCH) ./build.sh

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
	rm -rf pkg-cache/
