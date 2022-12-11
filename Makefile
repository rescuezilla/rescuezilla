.DEFAULT_GOAL := jammy
.PHONY: all focal impish jammy i386 deb sfdisk.v2.20.1.amd64 partclone.restore.v0.2.43.amd64 partclone-latest partclone-utils partclone-nbd install test integration-test clean-build-dir clean clean-all

# FIXME: Properly specify the build artifacts to allow the GNU make to actually be smart about what gets built and when.
# FIXME: This lack of specifying dependency graph means requires eg, `make focal` and `make impish` has to be done as separate invocations
#        and things get recompiled when they don't need to be etc.
# TODO:  Read the GNU make manual: https://www.gnu.org/software/make/manual/html_node/index.html and update this Makefile accordingly.
#
# FIXME: Somewhat related -- Improve build environment's ability to compile software (https://github.com/rescuezilla/rescuezilla/issues/150)

BASE_BUILD_DIRECTORY ?= $(shell pwd)/build

# Set threads variable to N-1 cpu cores.
THREADS = `cat /proc/cpuinfo | grep process | tail -1 | cut -d":" -f2 | cut -d" " -f2`

all: focal

buildscripts = build.sh chroot.steps.part.1.sh chroot.steps.part.2.sh

# ISO image based on Ubuntu 20.04 Focal LTS (Long Term Support) 64bit
focal: ARCH=amd64
focal: CODENAME=focal
export ARCH CODENAME
focal: deb sfdisk.v2.20.1.amd64 partclone-latest partclone-utils partclone-nbd $(buildscripts)
	BASE_BUILD_DIRECTORY=$(BASE_BUILD_DIRECTORY) ./build.sh

# ISO image based on Ubuntu 21.10 Impish 64bit as a temporary measure to provide a newer Linux kernel for better support for
# recent hardware because Ubuntu 20.04 Focal immediately offer a Hardware Enablement / LTS Enablement Linux kernel for those
# releases.
impish: ARCH=amd64
impish: CODENAME=impish
export ARCH CODENAME
impish: deb sfdisk.v2.20.1.amd64 partclone-latest partclone-utils partclone-nbd $(buildscripts)
	BASE_BUILD_DIRECTORY=$(BASE_BUILD_DIRECTORY) ./build.sh
	
jammy: ARCH=amd64
jammy: CODENAME=jammy
export ARCH CODENAME
jammy: deb sfdisk.v2.20.1.amd64 partclone-latest partclone-utils partclone-nbd $(buildscripts)
	BASE_BUILD_DIRECTORY=$(BASE_BUILD_DIRECTORY) ./build.sh	

# ISO image based on Ubuntu 18.04 Bionic LTS (Long Term Support) 32bit (the last 32bit/i386 Ubuntu LTS release)
i386: ARCH=i386
i386: CODENAME=bionic
export ARCH CODENAME
i386: deb $(buildscripts)
	BASE_BUILD_DIRECTORY=$(BASE_BUILD_DIRECTORY) ./build.sh

deb: DEB_BUILD_DIR=$(abspath $(BASE_BUILD_DIRECTORY))/deb
deb:
	mkdir --parents $(DEB_BUILD_DIR)
	cd src/apps/rescuezilla/ && DEB_BUILD_DIR=$(DEB_BUILD_DIR) $(MAKE) && mv $(DEB_BUILD_DIR)/rescuezilla_*.deb  $(DEB_BUILD_DIR)/../
	cd src/apps/graphical-shutdown/ && DEB_BUILD_DIR=$(DEB_BUILD_DIR) $(MAKE) && mv $(DEB_BUILD_DIR)/graphical-shutdown_*.deb  $(DEB_BUILD_DIR)/../

# Build AMD64 binaries for the version of 'sfdisk' and 'partclone' used on Redo Backup v1.0.4, to maximize backwards compatibility
# when restoring backups created with Redo Backup v1.0.4, because both those applications appear to have broken backwards compatibility. [1]
#
# Note: For Rescuezilla i386, simply version controlling the exact binary used by Redo Backup v1.0.4 (originally from Ubuntu 12.04) has been
# sufficient to achieve working backwards compatibility in all test cases so far.
#
# [1] For full details, see: https://github.com/rescuezilla/rescuezilla/issues/77

sfdisk.v2.20.1.amd64: SRC_DIR=$(shell pwd)/src/third-party/util-linux
sfdisk.v2.20.1.amd64: AMD64_BUILD_DIR=$(BASE_BUILD_DIRECTORY)/$(CODENAME).$(ARCH)
sfdisk.v2.20.1.amd64: UTIL_LINUX_BUILD_DIR=$(AMD64_BUILD_DIR)/util-linux
sfdisk.v2.20.1.amd64:
	mkdir --parents $(UTIL_LINUX_BUILD_DIR) $(AMD64_BUILD_DIR)/chroot/usr/sbin/
	cd $(UTIL_LINUX_BUILD_DIR) && $(SRC_DIR)/autogen.sh
	cd $(UTIL_LINUX_BUILD_DIR) && $(SRC_DIR)/configure --without-ncurses
	cd $(UTIL_LINUX_BUILD_DIR) && make CC='ccache cc' -j $(THREADS)
	mv $(UTIL_LINUX_BUILD_DIR)/fdisk/sfdisk $(AMD64_BUILD_DIR)/chroot/usr/sbin/sfdisk.v2.20.1.64bit

partclone.restore.v0.2.43.amd64: SRC_DIR=$(shell pwd)/src/third-party/partclone.v0.2.43
partclone.restore.v0.2.43.amd64: AMD64_BUILD_DIR=$(BASE_BUILD_DIRECTORY)/$(CODENAME).$(ARCH)
partclone.restore.v0.2.43.amd64: PARTCLONE_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone.v0.2.43
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
	cd $(PARTCLONE_BUILD_DIR) && make CC='ccache cc' -j $(THREADS)
	mv $(PARTCLONE_BUILD_DIR)/src/partclone.restore $(AMD64_BUILD_DIR)/chroot/usr/sbin/partclone.restore.v0.2.43.64bit
	# FIXME: Building out-of-tree modifies two files in the source directory during the TravisCI docker build (but works fine on a local build)
	cd $(SRC_DIR) && git checkout -- config.h.in configure

partclone-latest: SRC_DIR=$(shell pwd)/src/third-party/partclone-latest
partclone-latest: AMD64_BUILD_DIR=$(BASE_BUILD_DIRECTORY)/$(CODENAME).$(ARCH)
partclone-latest: PARTCLONE_LATEST_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone-latest
partclone-latest: PARTCLONE_PKG_VERSION=0.3.20
partclone-latest:
	# DANGER: Deletes build folder recursively. This can end very badly if a variable is not defined correctly.
	# TODO: FIX THIS
	rm -rf $(PARTCLONE_LATEST_BUILD_DIR)
	mkdir --parents $(PARTCLONE_LATEST_BUILD_DIR) $(AMD64_BUILD_DIR)/chroot/
	# TODO: Remove need to copy the source folder to destination
	rsync -rP "$(SRC_DIR)/" "$(PARTCLONE_LATEST_BUILD_DIR)/"
	cd $(PARTCLONE_LATEST_BUILD_DIR) && autoreconf -i
	cd $(PARTCLONE_LATEST_BUILD_DIR) && ./configure --enable-ncursesw --enable-static --enable-extfs --enable-reiser4 --enable-ntfs --enable-fat --enable-exfat --enable-hfsp --enable-apfs --enable-btrfs --enable-minix --enable-f2fs --enable-nilfs2
	cd $(PARTCLONE_LATEST_BUILD_DIR) && make CC='ccache cc' -j $(THREADS)
	# Create deb package from a standard Makefile's `make install` using the checkinstall tool (for cleaner uninstall)
	cd $(PARTCLONE_LATEST_BUILD_DIR) && checkinstall --install=no --pkgname partclone --pkgversion $(PARTCLONE_PKG_VERSION) --pkgrelease 1 --maintainer 'rescuezilla@gmail.com' -D --default  make CC='ccache cc' -j $(THREADS) install
	mv $(PARTCLONE_LATEST_BUILD_DIR)/partclone_$(PARTCLONE_PKG_VERSION)-1_amd64.deb $(AMD64_BUILD_DIR)/chroot/

# Builds partclone-utils, which contains some very useful utilities for working with partclone images.
partclone-utils: SRC_DIR=$(shell pwd)/src/third-party/partclone-utils
partclone-utils: AMD64_BUILD_DIR=$(BASE_BUILD_DIRECTORY)/$(CODENAME).$(ARCH)
partclone-utils: PARTCLONE_UTILS_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone-utils
partclone-utils:
	mkdir --parents $(PARTCLONE_UTILS_BUILD_DIR) $(AMD64_BUILD_DIR)/chroot/
	# FIXME: Want to build out-of-tree (in a build folder), but autotools doesn't make this easy like CMake, so copy the entire source folder to be the build folder.
	cp -r $(SRC_DIR)/* $(PARTCLONE_UTILS_BUILD_DIR)
	cd $(PARTCLONE_UTILS_BUILD_DIR) && autoreconf -i
	cd $(PARTCLONE_UTILS_BUILD_DIR) && ./configure
	# Create deb package from a standard Makefile's `make install` using the checkinstall tool (for cleaner uninstall)
	cd $(PARTCLONE_UTILS_BUILD_DIR) && checkinstall --install=no --pkgname partclone-utils --pkgversion 0.4.2 --pkgrelease 1 --maintainer 'rescuezilla@gmail.com' -D --default  make CC='ccache cc' -j $(THREADS) install
	mv $(PARTCLONE_UTILS_BUILD_DIR)/partclone-utils_0.4.2-1_amd64.deb $(AMD64_BUILD_DIR)/chroot/

# Builds partclone-nbd, a competitor project to partclone-utils that's also able to mount partclone images.
partclone-nbd: SRC_DIR=$(shell pwd)/src/third-party/partclone-nbd
partclone-nbd: AMD64_BUILD_DIR=$(BASE_BUILD_DIRECTORY)/$(CODENAME).$(ARCH)
partclone-nbd: PARTCLONE_NBD_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone-nbd
partclone-nbd:
	mkdir --parents $(PARTCLONE_NBD_BUILD_DIR) $(AMD64_BUILD_DIR)/chroot/
	cd $(PARTCLONE_NBD_BUILD_DIR) && cmake ${SRC_DIR}
	# Create deb package from a standard Makefile's `make install` using the checkinstall tool (for cleaner uninstall)
	cd $(PARTCLONE_NBD_BUILD_DIR) && checkinstall --install=no --pkgname partclone-nbd --pkgversion 0.0.3 --pkgrelease 1 --maintainer 'rescuezilla@gmail.com' -D --default  make CC='ccache cc' -j $(THREADS) install
	mv $(PARTCLONE_NBD_BUILD_DIR)/partclone-nbd_0.0.3-1_amd64.deb $(AMD64_BUILD_DIR)/chroot/

clean-build-dir:
	$(info * Unmounting chroot bind mounts)
	for dir in "$(BASE_BUILD_DIRECTORY)"/*; do \
          umount $$dir/chroot/dev/pts || true ; \
          umount $$dir/chroot/dev/    || true ; \
          umount $$dir/chroot/proc/   || true ; \
          umount $$dir/chroot/sys/    || true ; \
        done
	$(info * Deleting $(BASE_BUILD_DIRECTORY)/ directory)
	rm -rf "$(BASE_BUILD_DIRECTORY)"

# Print git status for all git submodules, to help debug when the working directory is non-pristine.
status: UTIL_LINUX_SRC_DIR=$(shell pwd)/src/third-party/util-linux
status: PARTCLONE_SRC_DIR=$(shell pwd)/src/third-party/partclone-latest
status:
	$(info * Top level Rescuezilla git status.)
	git status
	$(info * util-linux git submodule status.)
	cd $(UTIL_LINUX_SRC_DIR) && git status
	$(info * partclone git submodule status.)
	cd $(PARTCLONE_SRC_DIR) && git status

install: AMD64_BUILD_DIR=$(BASE_BUILD_DIRECTORY)/$(CODENAME).$(ARCH)
install: PARTCLONE_NBD_BUILD_DIR=$(AMD64_BUILD_DIR)/partclone-nbd
install: DEB_BUILD_DIR=$(BASE_BUILD_DIRECTORY)/deb
install: partclone-nbd deb
	DEBIAN_FRONTEND=noninteractive gdebi --non-interactive $(AMD64_BUILD_DIR)/chroot/partclone-nbd_0.0.3-1_amd64.deb
	DEBIAN_FRONTEND=noninteractive gdebi --non-interactive $(DEB_BUILD_DIR)/../rescuezilla_*.deb

test: RESCUEZILLA_TEST_DIR=$(shell pwd)/src/apps/rescuezilla/rescuezilla/usr/lib/python3/dist-packages/rescuezilla
test:
	python3 -m unittest discover -s $(RESCUEZILLA_TEST_DIR) -p 'test_*.py'

# Launch Rescuezilla's Integration Test Suite for end-to-end testing of Rescuezilla using VirtualBox and preprepared test images.
# Read the README file in the integration test folder for more information about how this works.
#
# Note: This command creates a large number of VirtualBox VMs as the current user.
# Note: Also the Rescuezilla ISO image to be built using `IS_INTEGRATION_TEST=true make`
integration-test: RESCUEZILLA_INTEGRATION_TEST_DIR=$(shell pwd)/src/integration-test
integration-test: INTEGRATION_TEST_LOG_DIR=$(BASE_BUILD_DIRECTORY)/integration-test-log-files/$(shell date +"%Y_%m_%d_%I_%M_%p")/
integration-test: INIT_LOG=$(INTEGRATION_TEST_LOG_DIR)/init.txt
# Number of threads with GNU Parallel (Consider setting to 1 when debugging). From man page:
# -P N     Number of jobslots on each machine. Run up to N jobs in parallel.  0 means as many as possible. Default is 100% which will run one job per CPU core on each machine.
# Currently keeping number of threads to 1 until an apparent problem with the interaction of GNU Parallel/TTYs and partclone is resolved.
integration-test: THREADS=1
integration-test:
	mkdir --parents $(INTEGRATION_TEST_LOG_DIR)
	$(RESCUEZILLA_INTEGRATION_TEST_DIR)/integration_test.py stop 2>&1 | tee $(INIT_LOG)
	$(RESCUEZILLA_INTEGRATION_TEST_DIR)/integration_test.py deinit 2>&1 | tee $(INIT_LOG)
	$(RESCUEZILLA_INTEGRATION_TEST_DIR)/integration_test.py init 2>&1 | tee $(INIT_LOG)
	$(info * Run all tests, return number of failures. Follow the log files using: tail -f $(INTEGRATION_TEST_LOG_DIR)/[...].txt)
	cd "$(RESCUEZILLA_INTEGRATION_TEST_DIR)/tests/" && ls test.*.sh | parallel -P$(THREADS) --tty "bash {} | tee \"$(INTEGRATION_TEST_LOG_DIR)/{}.log_file.txt\""

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

### Helper targets to simplify running in Docker

docker-build:
	docker build --no-cache=true --tag builder.image .

docker-run:
	docker run --rm --detach --privileged --name=builder.container --volume=$(shell pwd):/home/rescuezilla/ builder.image sleep infinity
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container ./git_add_safe_directory.sh

docker-stop:
	docker stop builder.container

docker-add-safe-directory:
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container ./git_add_safe_directory.sh

docker-test:
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container make test

docker-status:
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container make status

# Start an interactive bash session for live debugging
docker-bash:
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container /bin/bash

docker-deb:
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container make deb

docker-jammy:
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container make jammy

docker-focal:
	docker exec --interactive --workdir=/home/rescuezilla/ builder.container make focal

