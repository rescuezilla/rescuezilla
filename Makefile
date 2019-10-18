.DEFAULT_GOAL := iso-image

iso-image: build.sh chroot.steps.part.1.sh chroot.steps.part.2.sh
	./build.sh

clean-build-dir:
	$(info * Deleting build/ directory)
	umount build/chroot/dev/pts || true
	umount build/chroot/dev/ || true
	umount build/chroot/proc/ || true
	umount build/chroot/sys/ || true
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
