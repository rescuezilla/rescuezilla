.DEFAULT_GOAL := amd64
.PHONY: all amd64 groovy i386 deb sfdisk.v2.20.1.amd64 partclone.restore.v0.2.43.amd64 partclone-utils partclone-nbd clean-build-dir clean clean-all

all: amd64 groovy i386

buildscripts = build.sh chroot.steps.part.1.sh chroot.steps.part.2.sh

# ISO image based on Ubuntu 20.04 Focal LTS (Long Term Support) 64bit
amd64: ARCH=amd64
amd64: CODENAME=focal
export ARCH CODENAME
amd64: deb sfdisk.v2.20.1.amd64 partclone.restore.v0.2.43.amd64 partclone-utils partclone-nbd $(buildscripts)
	./build.sh

# ISO image based on Ubuntu 20.10 Groovy 64bit as a temporary measure to provide a newer Linux kernel for better support for
# recent hardware because Ubuntu 20.04 Focal doesn't offer a Hardware Enablement / LTS Enablement Linux kernel for 20.04
# based on the Ubuntu 20.10 kernel (but will for 21.04, 21.10 etc)
groovy: ARCH=amd64
groovy: CODENAME=groovy
export ARCH CODENAME
groovy: deb sfdisk.v2.20.1.amd64 partclone.restore.v0.2.43.amd64 partclone-utils partclone-nbd $(buildscripts)
	./build.sh

# ISO image based on Ubuntu 18.04 Bionic LTS (Long Term Support) 32bit (the last 32bit/i386 Ubuntu LTS release)
i386: ARCH=i386
i386: CODENAME=bionic
export ARCH CODENAME
i386: deb $(buildscripts)
	./build.sh

deb: BASE_BUILD_DIR=$(shell pwd)/build/deb/
deb:
	cd src/apps/rescuezilla/ && BUILD_DIR=$(BASE_BUILD_DIR) $(MAKE) && mv $(BASE_BUILD_DIR)/rescuezilla_*.deb  $(BASE_BUILD_DIR)/../
	cd src/apps/graphical-shutdown/ && BUILD_DIR=$(BASE_BUILD_DIR) $(MAKE) && mv $(BASE_BUILD_DIR)/graphical-shutdown_*.deb  $(BASE_BUILD_DIR)/../

# Build AMD64 binaries for the version of 'sfdisk' and 'partclone' used on Redo Backup v1.0.4, to maximize backwards compatibility
# when restoring backups created with Redo Backup v1.0.4, because both those applications appear to have broken backwards compatibility. [1]
#
# Note: For Rescuezilla i386, simply version controlling the exact binary used by Redo Backup v1.0.4 (originally from Ubuntu 12.04) has been
# sufficient to achieve working backwards compatibility in all test cases so far.
#
# [1] For full details, see: https://github.com/rescuezilla/rescuezilla/issues/77

sfdisk.v2.20.1.amd64: SRC_DIR=$(shell pwd)/src/third-party/util-linux
sfdisk.v2.20.1.amd64: AMD64_BUILD_DIR=$(shell pwd)/build/$(CODENAME).$(ARCH)
sfdisk.v2.20.1.amd64: UTIL_LINUX_BUILD_DIR=$(AMD64_BUILD_DIR)/util-linux
sfdisk.v2.20.1.amd64:
	mkdir --parents $(UTIL_LINUX_BUILD_DIR) $(AMD64_BUILD_DIR)/chroot/usr/sbin/
	cd $(UTIL_LINUX_BUILD_DIR) && $(SRC_DIR)/autogen.sh
	cd $(UTIL_LINUX_BUILD_DIR) && $(SRC_DIR)/configure --without-ncurses
	cd $(UTIL_LINUX_BUILD_DIR) && make
	mv $(UTIL_LINUX_BUILD_DIR)/fdisk/sfdisk $(AMD64_BUILD_DIR)/chroot/usr/sbin/sfdisk.v2.20.1.64bit

partclone.restore.v0.2.43.amd64: SRC_DIR=$(shell pwd)/src/third-party/partclone
partclone.restore.v0.2.43.amd64: AMD64_BUILD_DIR=$(shell pwd)/build/$(CODENAME).$(ARCH)
partclone.restore.v0.2.43.amd64: PARTCLONE_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone
partclone.restore.v0.2.43.amd64:
	mkdir --parents $(PARTCLONE_BUILD_DIR) $(AMD64_BUILD_DIR)/chroot/usr/sbin/
	# Builds partclone v0.2.43, but disables support for the following filesystems: XFS, reiserfs, UFS, VMFS and JFS.
	# Building with these filesystems fails, apparently because partclone uses patched versions of: xfsprogs,
	# progsreiserfs, reiser4progs, ufsutils, vmfs-tools and jfsutils [1].
	#
	# Fortunately, Redo Backup v1.0.4 does not contain the partclone binaries for these filesystems,
	# /usr/sbin/partclone.{xfs,reiserfs,ufs,vmfs,jfs}, so the inability for the partclone.restore.v0.2.43 executable
	# being built to restore those filesystems does not adversely affect Rescuezilla providing complete backwards
	# compatibility. Notably, Redo Backup v1.0.4 supports reiser4 (not to be confused with reiserfs), and
	# reiser4 / reiser4progs *is* part of the list of dependencies which partclone patches. However, a minor fix to
	# some broken build script logic was all that was needed for partclone v0.2.43 to build with reiser4 support.
	#
	# Thus, the partclone.restore v0.2.43 appears to able to provide full backwards compatibility on AMD64 builds for
	# backups made with Redo Backup v1.0.4. [2]
	#
	# [1] https://free.nchc.org.tw/drbl-core/pool/drbl/dev/
	# [2] For complete details, see: https://github.com/rescuezilla/rescuezilla/issues/77
	cd $(PARTCLONE_BUILD_DIR) && $(SRC_DIR)/configure --enable-static --enable-extfs --enable-reiser4 --enable-hfsp --enable-fat --enable-ntfs --enable-btrfs
	cd $(PARTCLONE_BUILD_DIR) && make
	mv $(PARTCLONE_BUILD_DIR)/src/partclone.restore $(AMD64_BUILD_DIR)/chroot/usr/sbin/partclone.restore.v0.2.43.64bit
	# FIXME: Building out-of-tree modifies two files in the source directory during the TravisCI docker build (but works fine on a local build)
	cd $(SRC_DIR) && git checkout -- config.h.in configure

# Builds partclone-utils, which contains some very useful utilities for working with partclone images.
partclone-utils: SRC_DIR=$(shell pwd)/src/third-party/partclone-utils
partclone-utils: AMD64_BUILD_DIR=$(shell pwd)/build/$(CODENAME).$(ARCH)
partclone-utils: PARTCLONE_UTILS_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone-utils
partclone-utils:
	mkdir --parents $(PARTCLONE_UTILS_BUILD_DIR)
	# FIXME: Want to build out-of-tree (in a build folder), but autotools doesn't make this easy like CMake, so copy the entire source folder to be the build folder.
	cp -r $(SRC_DIR)/* $(PARTCLONE_UTILS_BUILD_DIR)
	cd $(PARTCLONE_UTILS_BUILD_DIR) && autoreconf -i
	cd $(PARTCLONE_UTILS_BUILD_DIR) && ./configure
	# Create deb package from a standard Makefile's `make install` using the checkinstall tool (for cleaner uninstall)
	cd $(PARTCLONE_UTILS_BUILD_DIR) && checkinstall --install=no --pkgname partclone-utils --pkgversion 0.4.2 --pkgrelease 1 --maintainer 'rescuezilla@gmail.com' -D --default  make install
	mv $(PARTCLONE_UTILS_BUILD_DIR)/partclone-utils_0.4.2-1_amd64.deb $(AMD64_BUILD_DIR)/chroot/

# Builds partclone-nbd, a competitor project to partclone-utils that's also able to mount partclone images.
partclone-nbd: SRC_DIR=$(shell pwd)/src/third-party/partclone-nbd
partclone-nbd: AMD64_BUILD_DIR=$(shell pwd)/build/$(CODENAME).$(ARCH)
partclone-nbd: PARTCLONE_NBD_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone-nbd
partclone-nbd:
	mkdir --parents $(PARTCLONE_NBD_BUILD_DIR)
	cd $(PARTCLONE_NBD_BUILD_DIR) && cmake ${SRC_DIR}
	# Create deb package from a standard Makefile's `make install` using the checkinstall tool (for cleaner uninstall)
	cd $(PARTCLONE_NBD_BUILD_DIR) && checkinstall --install=no --pkgname partclone-nbd --pkgversion 0.0.3 --pkgrelease 1 --maintainer 'rescuezilla@gmail.com' -D --default  make install
	mv $(PARTCLONE_NBD_BUILD_DIR)/partclone-nbd_0.0.3-1_amd64.deb $(AMD64_BUILD_DIR)/chroot/

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

# Print git status for all git submodules, to help debug when the working directory is non-pristine.
status: UTIL_LINUX_SRC_DIR=$(shell pwd)/src/third-party/util-linux
status: PARTCLONE_SRC_DIR=$(shell pwd)/src/third-party/partclone
status:
	$(info * Top level Rescuezilla git status.)
	git status
	$(info * util-linux git submodule status.)
	cd $(UTIL_LINUX_SRC_DIR) && git status
	$(info * partclone git submodule status.)
	cd $(PARTCLONE_SRC_DIR) && git status

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
