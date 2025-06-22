#  Rescuezilla v2.6.1 (unreleased)

* Fixed regression where swap partitions stayed unintendedly mounted causing restore and clone operations to destination disks containing Linux swap partitions to fail ([#515](https://github.com/rescuezilla/rescuezilla/issues/515#issuecomment-2994462320))
    * Impacted Ubuntu 23.10 (Mantic) and newer variants of Ubuntu 24.04 (Noble) and Ubuntu 24.10 (Oracular) so on the newer variants since Rescuezilla v2.5 (2024-05-12) 
* Renabled Image Explorer (beta) after it was temporarily disabled in v2.6.0 ([#557](https://github.com/rescuezilla/rescuezilla/issues/557))
    * Switched packaging the underlying "partclone-nbd" executable from the "checkinstall" wrapper to a more canonical packaging strategy using CMake's CPack (to avoid bug in 'checkinstall' script)
* Enabled Firefox on the Ubuntu 24.10 (Oracular) release after it was temporarily excluded in v2.6.0 ([#556](https://github.com/rescuezilla/rescuezilla/issues/556))
    * Switched to installing Firefox deb package from "packages.mozilla.org" rather than the "mozillateam" Ubuntu Personal Packaging Archive (thanks engstk!)
    * The "mozillateam" Ubuntu Personal Packaging Archive now wraps snap-based packages like the official Ubuntu repositories, which remain incompatible with Rescuezilla's "chroot"-based build scripts ([#364](https://github.com/rescuezilla/rescuezilla/issues/364))

#  Rescuezilla v2.6 (2025-03-23)

* Updated the UEFI Secure Boot shim package to v1.58 after a Windows 11 update revoked older shims by incrementing the minimum "SBAT generation"([#525](https://github.com/rescuezilla/rescuezilla/issues/525))
    * This fixes any "SBAT self-check failed" errors to ensure Rescuezilla continues boot on UEFI Secure Boot enabled systems which require the latest "SBAT generation"
    * This also fixes the "revoked UEFI bootloader" message warning when creating a bootable USB stick using Rufus
* Replaced Ubuntu 23.10 (Mantic) and Ubuntu 22.10 (Lunar) builds with build based on Ubuntu 24.10 (Oracular) for best support of new hardware 
    * Temporarily does not include Mozilla Firefox on Oracular release until switched to new source ([#556](https://github.com/rescuezilla/rescuezilla/issues/556))
    * Image Explorer (beta) temporarily out-of-service across variants ([#557](https://github.com/rescuezilla/rescuezilla/issues/557))
* Fixed querying drives with the Bionic 32-bit version, which broke since Rescuezilla v2.5 due to using the --merge feature introduced in util-linux v2.34 ([#509](https://github.com/rescuezilla/rescuezilla/issues/509), [#531](https://github.com/rescuezilla/rescuezilla/issues/531))
* Skips GPG check on Bionic 32-bit release to fix build (temporarily) until better solution identified ([#538](https://github.com/rescuezilla/rescuezilla/issues/538))
* Upgraded to latest partclone `v0.3.33` (released mid-July 2024) from partclone `v0.3.27` (released October 2023)
* Upgrades memtest86+ v5.31 to memtest86+ v7.00 ([#540](https://github.com/rescuezilla/rescuezilla/issues/540))
* Updated the build environment OS to Ubuntu 24.04 (Noble) from Ubuntu 22.04 (Jammy) ([#539](https://github.com/rescuezilla/rescuezilla/issues/539)), which was needed for the UEFI Secure Boot "SBAT" fix above 
* Many new and significantly updated translations submitted using Weblate:
    * Persian/فارسی (fa-IR) (in-progress)
    * Finnish/Suomi (fi-FI)
    * Romanian/Rolână (ro-RO) (in-progress)
    * Tamil/தமிழ் (ta-IN)
    * Norwegian Bokmål/Norsk Bokmål (nb-NO) (significantly updated)
    * Japanese/日本語 (ja-JP) (significantly updated)

# Rescuezilla v2.5.1 (2024-09-08)

* Stops running the `ntfsfix --clear-dirty` on NTFS filesystems on the SOURCE DISK during backup and clone operations ([#466](https://github.com/rescuezilla/rescuezilla/issues/466))
  * Running this command (the only command in Rescuezilla that modifies the source disk) appears to be the root cause of a critical severity error that impacted a small number of (hibernated) Windows disks since the command was added in Rescuezilla v2.3 (2021-12-24) where creating a backup image or clone appears to cause some kind of corruption that can break the Windows boot with a Blue Screen of Death, possibly due to corruption in the Windows BCD (Boot Configuration Data)
  * However, I still have not been able to reproduce the error in despite many hours of testing
  * Removing this command will likely mean more 'hibernated NTFS disk' errors on backup or clone of Windows disks if not booting into Rescuezilla with the 'Restart' Start Menu command -- but removing the apparently dangerous command is obviously worthwhile
* Fixed 'stuck at 0%' bug for backup and cloning when only one partition is selected, bug introduced in v2.5.0 ([#482](https://github.com/rescuezilla/rescuezilla/issues/482))
* Fixed several user-interface disconnects where upon an error the user-interface correctly jumped to the Summary page but the backup, clone or restore operation mistakenly continues in background, causing a disconnect in what the user-interface shows compared to the operation that's occurring. The cases identified were:
  * On backup/clone if an NTFS filesystem fails to unmount after being checked for Windows Boot Reserved partition information ([#501](https://github.com/rescuezilla/rescuezilla/issues/501))
  * On backup/clone/restore if a Logical Volume Manager (LVM) is fails to be shutdown ([#501](https://github.com/rescuezilla/rescuezilla/issues/501))
  * If partition fails to unmount when when a backup or clone operation ([#501](https://github.com/rescuezilla/rescuezilla/issues/501))
* Upgraded to latest partclone `v0.3.32` (released mid-July 2024) from partclone `v0.3.27` (released October 2023)
  * Examining the partclone projects commit log indicates key changes are:
    * Several partclone errors cases now no longer return success upon failure
    * Upgraded BTRFS support to BTRFS v6.8.1 from BTRFS v6.3.3

 # Rescuezilla v2.5 (2024-05-12)

* Adds release based on Ubuntu 24.04 (Noble), Ubuntu 23.10 (Mantic) and Ubuntu 23.04 (Lunar) for best support of new hardware
* Upgrades to latest partclone release `v0.3.27` (released October 2023) from `v0.3.20` (which was released in April 2022)
  * This should improve issues with BTRFS filesystems, as it supports BTRFS v6.3.3, rather than v5.11 ([#393](https://github.com/rescuezilla/rescuezilla/issues/393#issuecomment-1718658170))
* Added experimental command-line interface (CLI) ([#258](https://github.com/rescuezilla/rescuezilla/issues/258))
  * CLI should be considered EXPERIMENTAL and UNSTABLE, and behavior may change between versions without notice
  * CLI only supports images created by Clonezilla and Rescuezilla (the other supported formats coming in future)
  * CLI only supports backup, verify, restore and clone operations (mount and unmount operations coming in future)
* Integrated Rescuezilla into the automated integration test suite scripts, to hopefully enable faster project iteration
* Continue image scan after an error, so permission denied on irrelevant folders no longer block populating the image list
* Fixed issue causing backup of Linux md RAID devices containing MBR partition tables to fail ([#448](https://github.com/rescuezilla/rescuezilla/issues/448))
* Installs 'hashdeep' package as stop-gap command-line workaround for a specific user niche until Rescuezilla's UI handles it ([#441](https://github.com/rescuezilla/rescuezilla/issues/441))
* Fixed failing restore and clone operations when Rescuezilla v2.4.2 booted into Portuguese language, due to a minor typo ([#438](https://github.com/rescuezilla/rescuezilla/issues/438))
* Prevent laptops from sleeping when is lid closed ([#427](https://github.com/rescuezilla/rescuezilla/issues/427))

# Rescuezilla v2.4.2 (2023-03-05)

* Removes the Intel screen tearing fix introduced for v2.3 (2021-12-24), which should fix black screens on Intel graphics ([#281](https://github.com/rescuezilla/rescuezilla/issues/281#issuecomment-1345457445))
* Introduces Ubuntu 22.10 (Kinetic) for best support of recent hardware, but leaves default build as Ubuntu 22.04 (Jammy)
* Reintroduces a 32-bit (Intel i386) build, currently based on Ubuntu 18.04 (Bionic) (#232) after it was temporarily dropped in Rescuezilla v2.0 (2020-10-14) 
    * Note: Partclone backwards compatibility is imperfect and 32-bit release uses old Ubuntu repository partclone version, not latest compiled version
* Fixes Backup mode's broken SSH port field introduced in v2.4 ([#385](https://github.com/rescuezilla/rescuezilla/issues/385))
* Installs lxappearance ([#274](https://github.com/rescuezilla/rescuezilla/issues/274)), hexdump (bsdmainutils) ([#382](https://github.com/rescuezilla/rescuezilla/issues/382)), flashrom ([#388](https://github.com/rescuezilla/rescuezilla/issues/388))
* Installed packages which improve ability to mount encrypted drives with pcmanfm file manager ([#379](https://github.com/rescuezilla/rescuezilla/issues/379))
* Replaces out-of-service Travis-CI build bot integration with GitHub Actions, for improved quality-control, and to assist Rescuezilla contributors
* Many existing translations updated, but also added:
  * Albanian/Shqip (sq-AL) (Translation in-progress)
  * Lithuanian/Lietuvių (lt-LT)
  * Dutch/Nederlands (nl-NL)

# Rescuezilla v2.4.1 (2022-09-05)

* Fixed broken wifi after v2.4 broke it (due to a change in Ubuntu 22.04 Jammy [leading to a key package not being installed (#366)](https://github.com/rescuezilla/rescuezilla/issues/366#issuecomment-1214413260)
* Reintroduced ISO variant based on Ubuntu 20.04 (Focal), to assist users with AMD/Intel graphics
    * AMD/Intel graphics still expected to be broken on "Jammy" variant except when using Graphical Fallback Mode ([#351](https://github.com/rescuezilla/rescuezilla/issues/351))
* Fixed image verification for German language [(broken for all images in v2.4 German language mode, due to a typo in a translation string) (#352)]((https://github.com/rescuezilla/rescuezilla/issues/352))
    * Fixed similar fatal user-facing error messages caused by translation typos in the French, Danish and Catalan translations
* Add the font to fix display of the cross mark character "❌" in the image verification summary
* Fixed "stuck at 0%" progress bar when the destination is read-only ([#363](https://github.com/rescuezilla/rescuezilla/issues/363))
    * Added protection to prevent other unexpected situations from leading to the same behavior
* Many existing translations updated, but also added:
  * Thai/ภาษาไทย (th-TH)

# Rescuezilla v2.4 (2022-08-07)

* Replaces Ubuntu 21.10 (Impish) build with build based on Ubuntu 22.04 (Jammy) for best support of new hardware 
* Builds latest version of partclone from source code `v0.3.20`, instead of OS package ([#168](https://github.com/rescuezilla/rescuezilla/issues/168), [#309](https://github.com/rescuezilla/rescuezilla/issues/309), [#335](https://github.com/rescuezilla/rescuezilla/issues/335))
    * This fixes "unsupported feature" error for users of compressed BTRFS filesystems (such as Fedora Workstation 33 and newer)
* Removed old partclone v0.2.43 used to _maximize_ legacy Redo Backup compatibility (modern partclone still provides good backwards compatibility)
* Fixed execution of Clonezilla EFI NVRAM script to better correctly handle reboot on EFI systems (#348)
* Switched Firefox to using the Mozilla Team PPA repository, because new "snap" packaging is incompatible with Rescuezilla's build scripts ([#364](https://github.com/rescuezilla/rescuezilla/issues/364))
* Added ability to compress images using bzip2 algorithm ([#290](https://github.com/rescuezilla/rescuezilla/issues/290))
* Moved post-completion action to in-progress page ([#316](https://github.com/rescuezilla/rescuezilla/issues/316))
    *  **This has caused at least 1 user an issue during cloning, which I'm yet unable to reproduce: [#337](https://github.com/rescuezilla/rescuezilla/issues/337)**
* Added ability to set custom SSH port ([#336](https://github.com/rescuezilla/rescuezilla/issues/336))
* Many existing translations updated, but also added:
  * Arabic/ﺎﻠﻋﺮﺒﻳﺓ (ar-EG)
  * Catalan/Català (ca-ES) (Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/ca/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))
  * Czech/Čeština (cs-CZ) (Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/cs/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))
  * Hungarian/Magyar (hu-HU) Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/hu/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))
  * Slovak/Slovenčina (sk-SK) (Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/sk/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))

#  Rescuezilla Pre-release (2022-07-24) 

* Replaces Ubuntu 21.10 (Impish) build with build based on Ubuntu 22.04 (Jammy) for best support of new hardware
* Builds latest version of partclone from source code `v0.3.20`, instead of OS package ([#168](https://github.com/rescuezilla/rescuezilla/issues/168), [#309](https://github.com/rescuezilla/rescuezilla/issues/309), [#335](https://github.com/rescuezilla/rescuezilla/issues/335))
    * This fixes "unsupported feature" error for users of compressed BTRFS filesystems (such as Fedora Workstation 33 and newer)
* Removed old partclone v0.2.43 used to _maximize_ legacy Redo Backup compatibility (modern partclone still provides good backwards compatibility)
* Switched Firefox to using the Mozilla Team PPA repository, because new "snap" packaging is still incompatible with Rescuezilla's "chroot-based" build scripts ([#364](https://github.com/rescuezilla/rescuezilla/issues/364))

**KNOWN BUG: When cloning, user reported the auto-restart/auto-shutdown drop-down breaks the clone ([#337](https://github.com/rescuezilla/rescuezilla/issues/337))**. I tried in the "restore" mode on my environment with several images and it worked fine. This report is still being further investigated for the "clone" mode, but I didn't want it to block release of the Jammy upgrade.
  
# Rescuezilla Pre-release (2022-06-26) 

* Added ability to compress images using bzip2 algorithm ([#290](https://github.com/rescuezilla/rescuezilla/issues/290))
* Moved post-completion action to in-progress page ([#316](https://github.com/rescuezilla/rescuezilla/issues/316))
* Added ability to set custom SSH port ([#336](https://github.com/rescuezilla/rescuezilla/issues/336))
* Many existing translations updated, but also added:
  * Arabic/ﺎﻠﻋﺮﺒﻳﺓ (ar-EG) (translation now complete!)
  * Catalan/Català (ca-ES) (Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/ca/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))
  * Czech/Čeština (cs-CZ) (Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/cs/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))
  * Hungarian/Magyar (hu-HU) Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/hu/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))
  * Slovak/Slovenčina (sk-SK) (Translation [in-progress](https://hosted.weblate.org/translate/rescuezilla/-/sk/?offset=1&q=state%3A%3Ctranslated+AND+NOT+has%3Asuggestion&sort_by=-priority%2Cposition&checksum=))

# Rescuezilla v2.3.1 (2022-01-02) 

* Fixed "Clone always stuck at 0%" issue introduced in v2.3.0 ([#297](https://github.com/rescuezilla/rescuezilla/issues/297))
* Added Korean/한국어 translation (ko-KR) ([using Weblate](https://hosted.weblate.org/projects/rescuezilla/#languages))
* Significantly updated existing Italian/Italiano translation (it-IT) ([using Weblate](https://hosted.weblate.org/projects/rescuezilla/#languages))

# Rescuezilla v2.3 (2021-12-24) 

* Implemented image verification feature ([#30](https://github.com/rescuezilla/rescuezilla/issues/30))
* Adds "Rescue" option to ignore filesystem inconsistencies and bad sectors ([#237](https://github.com/rescuezilla/rescuezilla/issues/237))
* Replaces Ubuntu 21.04 (Hirsute) build with build based on Ubuntu 21.10 (Impish) for best support of new hardware
* Added ability to restore and explore images created by "Apart" partclone GUI ([#230](https://github.com/rescuezilla/rescuezilla/issues/230))
* Improved image scanning to try to fix report of where some images not scanning except with Browse ([#251](https://github.com/rescuezilla/rescuezilla/issues/251))
* Fixed display of LVM shutdown error message ([#250](https://github.com/rescuezilla/rescuezilla/issues/250))
* Displayed serial number of drives in response to feedback ([#227](https://github.com/rescuezilla/rescuezilla/issues/227))
* Added lxappearance package to make it easy to set the dark theme ([#275](https://github.com/rescuezilla/rescuezilla/issues/275))
* Added ability to open file manager as root using right-click ([#281](https://github.com/rescuezilla/rescuezilla/issues/281))
* Added user-provided Intel Xorg conf file to hopefully stop screen tearing ([#281](https://github.com/rescuezilla/rescuezilla/issues/281))
* Fixed issue preventing restoring of images created by FSArchiver/qtfsarchiver ([#255](https://github.com/rescuezilla/rescuezilla/issues/255))
* Switched to "xdg-open" to launch file manager and web browser, rather than hardcoding pcmanfm and Firefox
* Added (or significantly updated) translations:
  * Hebrew/עִברִית (he-IL) ([#244](https://github.com/rescuezilla/rescuezilla/issues/244))
  * Vietnamese/Tiếng Việt (vi-VN) ([#263](https://github.com/rescuezilla/rescuezilla/issues/263))
  * Danish/Dansk (da-DK) ([#248](https://github.com/rescuezilla/rescuezilla/issues/248))
  * Russian/Русский (ru-RU) ([#270](https://github.com/rescuezilla/rescuezilla/issues/270))

# Rescuezilla v2.2 (2021-06-04) 


* Implemented cloning (direct 'device-to-device' mode) ([#47](https://github.com/rescuezilla/rescuezilla/issues/47))
* Added ability to restore and explore all virtual machine image formats supported by qemu-nbd ([#192](https://github.com/rescuezilla/rescuezilla/issues/192))
  (VirtualBox’s VDI, VMWare’s VMDK, Qemu’s QCOW2, HyperV's VHDx, raw .dd/.img and many more) 
* Added ability to restore and explore images created by all remaining open-source imaging frontends ([#194](https://github.com/rescuezilla/rescuezilla/issues/194))
  (Redo Rescue, Foxclone, FSArchiver, Redo v0.9.2 and very-early handling of FOG Project images)
* Added ability to customize compression format (gzip, zstandard, uncompressed) and compression level ([#170](https://github.com/rescuezilla/rescuezilla/issues/170))
* Implemented remaining Clonezilla image restore logic to improve handling of many corner cases: ([#146](https://github.com/rescuezilla/rescuezilla/issues/146))
  * Grows filesystem to fit partition size (but almost always filesystem size is already equal to partition size)
  * Runs filesystem check on all restored filesystems
  * Clears the NTFS volume dirty flag, for source during backup/clone and destination for restore/clone
  * Removes the udev MAC address records (if any) using Clonezilla script
  * Re-install the syslinux bootloader (if any) using Clonezilla script
  * Re-install the GRUB bootloader (if any) using Clonezilla script
  * Update initramfs (if any) using Clonezilla script
  * Relocates all NTFS filesystems using geometry from sfdisk or (if available) EDD (Enhanced Disk Device)
  * Restores LVM VG metadata with --force to match a recent Clonezilla patch referring to thin-pool LVs 
  * Ensures each LVM VG metadata once is only restored once to support newer versions of vgcfgrestore
  * Updates EFI NVRAM for the boot device
* Replaces Ubuntu 20.10 (Groovy) build with build based on Ubuntu 21.04 (Hirsute) for best support of new hardware
* Added option to shutdown or reboot after operation completes successfully ([#165](https://github.com/rescuezilla/rescuezilla/issues/165))
* Added ability to connect to NFS and SSH (SFTP) network shared folders ([#81](https://github.com/rescuezilla/rescuezilla/issues/81), [#118](https://github.com/rescuezilla/rescuezilla/issues/118))
* Added ability to write a description for backup images ([#137](https://github.com/rescuezilla/rescuezilla/issues/137))
* Added ability to make a screenshot by pressing Print Screen ([#166](https://github.com/rescuezilla/rescuezilla/issues/166))
* Switched to using [Weblate](https://github.com/rescuezilla/rescuezilla/wiki/Translations-HOWTO) to manage translations:
* Added translations:
  * Swedish/Svenska (sv-SE) ([#186](https://github.com/rescuezilla/rescuezilla/issues/186))
  * Turkish/Türkçe (tr-TR) ([#89](https://github.com/rescuezilla/rescuezilla/issues/89))
  * Chinese (Simplified)/中文(简体) (zh-CN) ([#191](https://github.com/rescuezilla/rescuezilla/issues/191))
  * Chinese (Traditional)/中文(繁體) (zh-Hant)
  * Norwegian Bokmål/Norsk Bokmål (nb-NO)
  * Russian/Русский (ru-RU) \[[translation in-progress](https://github.com/rescuezilla/rescuezilla/issues/270#issuecomment-939196164)\]
  * Dansk/Danish (da-DK)
* Added scrollbar to GRUB boot menu to handle increasing number of languages
* Removed 'localepurge' whitelist since number of translations is growing

# Rescuezilla v2.1.3 (2021-01-29) 

* Added scrollbars to improve usability on low-resolution displays ([#164](https://github.com/rescuezilla/rescuezilla/issues/164))
* Fixed automatic maximization of Rescuezilla's main window ([#164](https://github.com/rescuezilla/rescuezilla/issues/164))
* Added Greek/Ελληνικά (el-GR) translation by tkatsageorgis (ευχαριστώ!) ([#171](https://github.com/rescuezilla/rescuezilla/issues/171))
* Added Japanese/日本語 (ja-JP) translation by AE720 (ありがとう！) ([#176](https://github.com/rescuezilla/rescuezilla/issues/176))

# Rescuezilla v2.1.2 (2021-01-01) 

* Fixed incorrect filename pattern match that prevented booting after restoring [MBR disks from **_some_** locations (#162)](https://github.com/rescuezilla/rescuezilla/issues/162)
* Removed "Are You Sure" prompt on Image Explorer (beta) unmount

# Rescuezilla v2.1.1 (2020-12-14) 

* Fixed restoring dual-boot GRUB bootloader on MBR systems after bug was introduced in v2.1 ([#155](https://github.com/rescuezilla/rescuezilla/issues/155))
* Fixed display of error message if a partclone backup fails ([#122](https://github.com/rescuezilla/rescuezilla/issues/122#issuecomment-744176185))
* Skipped making second backup of Extended Boot Record using partclone to better match Clonezilla
* Removed partclone images on backup failure to better match Clonezilla's behavior
* Added "Are You Sure" prompt to Image Explorer (beta) so users understand the limitations
* Added Italian/Italiano (it-IT) translation by AlexTux87  (Grazie!) ([#154](https://github.com/rescuezilla/rescuezilla/issues/154))
* [**RESCUEZILLA IS OPEN FOR TRANSLATIONS!**](https://github.com/rescuezilla/rescuezilla/wiki/Translations-HOWTO)

# Rescuezilla v2.1 (2020-12-12) 

* Added ‘Image Explorer’ (beta) to easily mount partclone images and extract files ([#20](https://github.com/rescuezilla/rescuezilla/issues/20))
  * Currently based on `partclone-nbd`
  * Rescuezilla intends on switching to using the more popular `partclone-utils` project (which can also mount `ntfsclone` images)
  * Accessing files from **uncompressed** images (created by Clonezilla's Expert Mode) is _extremely_ fast even for very large images
  * Both Clonezilla and Rescuezilla currently default to gzip compression, which requires decompressing a lot of data and makes mounting and exploring images over 50GB too slow.
  * A future release of Rescuezilla will change the default compression format so mounting large images is always fast and efficient
* Switched primary release to new build based on Ubuntu 20.10 (Groovy) for improved NVidia graphics card support ([#115](https://github.com/rescuezilla/rescuezilla/issues/115))
* Fixed slow backup speed after mistakenly switching away from pigz multithreaded compression ([#125](https://github.com/rescuezilla/rescuezilla/issues/125))
* Fixed scan issue on some Redo Backup v0.9.8-v1.0.4, Rescuezilla v1.0.5-v1.0.6.1 images ([#127](https://github.com/rescuezilla/rescuezilla/issues/127))
* Added ability to cancel the image scan by closing the progress bar popup ([#126](https://github.com/rescuezilla/rescuezilla/issues/126))
* Displayed more progress details during drive query and image scan ([#126](https://github.com/rescuezilla/rescuezilla/issues/126))
* Ensured that (unlike Clonezilla), disks with >1024MB still have 1MB post-MBR gap backup ([#131](https://github.com/rescuezilla/rescuezilla/issues/131))
* Ensured all post-MBR gap always restored (whether 1MB or 1024MB), not just the first 256KB ([#131](https://github.com/rescuezilla/rescuezilla/issues/131))
* Fixed post-MBR gap backup being one 512-byte sector too large ([#131](https://github.com/rescuezilla/rescuezilla/issues/131))
* Fixed ability to specify the SMB/CIFS network share version field ([#140](https://github.com/rescuezilla/rescuezilla/issues/140))
* Fixed “dev-fs.list” image scanning errors with recent Clonezilla “testing” releases ([#139](https://github.com/rescuezilla/rescuezilla/issues/139))
* Ignored “sector-size” line in sfdisk partition table to maximize forward compatibility ([#147](https://github.com/rescuezilla/rescuezilla/issues/147))
* Considered failure to query optional drive geometry information as non-fatal error ([#122](https://github.com/rescuezilla/rescuezilla/issues/122))
* Ensured .info gets created for Microsoft Reserved Partitions to better match Clonezilla ([#133](https://github.com/rescuezilla/rescuezilla/issues/144))
* Fixed rounding error for drive/partition sizes, and removed python hurry.filesize library ([#148](https://github.com/rescuezilla/rescuezilla/issues/148))
* Improved handling of read-only destination drives during backup
* Added partclone-nbd v0.0.3 and partclone-utils v0.4.2 applications ([#20](https://github.com/rescuezilla/rescuezilla/issues/20))
* Added Brazilian Portuguese/Português brasileiro (pt-BR) translation by vinicioslc (obrigado!) ([#128](https://github.com/rescuezilla/rescuezilla/issues/128))
* Added Polish/Polski (pl-PL) translation by zeit439  (dzięki!) ([#135](https://github.com/rescuezilla/rescuezilla/issues/135))

# Rescuezilla v2.0 (2020-10-14) 

* Switched to creating backups in Clonezilla format for full interoperability with Clonezilla: Rescuezilla is now a drop-in replacement to Clonezilla!
  In other words, backups created using Clonezilla can be restored using Rescuezilla, and vice versa :)
* Warning: Backups created with Rescuezilla v2.0 cannot be restored using earlier versions of Rescuezilla. Backups created with older versions of Rescuezilla can still of course be restored with v2.0
* Added ability to restore individual partitions, and optionally to not overwrite partition table ([#46](https://github.com/rescuezilla/rescuezilla/issues/46))
* Rewrote the Rescuezilla frontend in the Python3 programming language ([#111](https://github.com/rescuezilla/rescuezilla/issues/111), [#49](https://github.com/rescuezilla/rescuezilla/issues/49), [#48](https://github.com/rescuezilla/rescuezilla/issues/48))
* Added backup/restore confirmation and summary pages, back button ([#6](https://github.com/rescuezilla/rescuezilla/issues/6))
* Improved exit code handling and error messages ([#29](https://github.com/rescuezilla/rescuezilla/issues/29), [#114](https://github.com/rescuezilla/rescuezilla/issues/114)), image selection ([#109](https://github.com/rescuezilla/rescuezilla/issues/109))
* Disabled Linux time sync to prevent hardware clock modification (thanks zebradots!) ([#107](https://github.com/rescuezilla/rescuezilla/issues/107))
* Added the ability to backup and restore software RAID (md) devices ([#45](https://github.com/rescuezilla/rescuezilla/issues/45))
* Added the ability to backup and restore SD card (mmcblk) devices ([#95](https://github.com/rescuezilla/rescuezilla/issues/95))
* Added filesystem-aware backup/restore of Linux Logical Volume Manager (LVM) ([#44](https://github.com/rescuezilla/rescuezilla/issues/44))
* [**RESCUEZILLA IS NOW OFFICIALLY OPEN FOR TRANSLATIONS!**](https://github.com/rescuezilla/rescuezilla/wiki/Translations-HOWTO)

# Rescuezilla v1.0.6.1 (2020-06-26) 

* Improved shutdown speed on 64-bit which was being [delayed]( https://bugs.launchpad.net/ubuntu/+source/pcmanfm/+bug/1878625) by the file manager application ([#87](https://github.com/rescuezilla/rescuezilla/issues/87))
* Fixed French, German and Spanish keyboard layout not being selected ([#99](https://github.com/rescuezilla/rescuezilla/issues/99))
* Skipped “Please remove the installation medium, then press ENTER” after shutdown ([#87](https://github.com/rescuezilla/rescuezilla/issues/87))
* Fixed mousepad text editor’s shortcuts and file-associations ([#98](https://github.com/rescuezilla/rescuezilla/issues/98))
* Added grub2-common package for /usr/sbin/grub-install executable, which was intended for v1.0.6 ([#50](https://github.com/rescuezilla/rescuezilla/issues/50))
* Fixed version string indicating that the TravisCI build bot used non-pristine build directory ([#102](https://github.com/rescuezilla/rescuezilla/issues/102))
* Tweaked Rescuezilla wallpaper, splash screen, icon for aesthetics

# Rescuezilla v1.0.6 (2020-06-18) 

* Added 64-bit version (this fixes the [slow transfer rates](https://github.com/rescuezilla/rescuezilla/issues/15#issuecomment-611541952) issue on systems with >16GB RAM) ([#3](https://github.com/rescuezilla/rescuezilla/issues/3))
* Added support for booting on EFI-only machines (including with Secure Boot enabled) [64-bit only] ([#1](https://github.com/rescuezilla/rescuezilla/issues/1))
* Switched ISOLINUX bootloader to GRUB affecting all boot approaches: BIOS, EFI and CD-ROM
* Upgraded OS base to Ubuntu 20.04 LTS (Focal) from 18.04 LTS (Bionic) [64-bit only] ([#51](https://github.com/rescuezilla/rescuezilla/issues/51))
* Ubuntu 20.04 has dropped 32-bit, so Rescuezilla 32-bit remains based on Ubuntu 18.04
* Fixed issue preventing backup/restore of hard drives smaller than typically ~40 megabytes ([#55](https://github.com/rescuezilla/rescuezilla/issues/55))
* Fixed broken GRUB backup affecting _some_ 1MiB-aligned filesystems on MBR-formatted disks, by copying all of “post-MBR gap” between MBR and first partition, not just typical 32KiB. ([#50](https://github.com/rescuezilla/rescuezilla/issues/50))
* Added GRUB packages to assist users who want to use Rescuezilla to perform a GRUB repair ([#50](https://github.com/rescuezilla/rescuezilla/issues/50))
* Fixed a “stuck at 0%” issue when paths contain certain special characters ([#15](https://github.com/rescuezilla/rescuezilla/issues/15#issuecomment-616976794))
* Removed false menu items such as “(Windows Boot Manager, )” by correctly merging items ([#69](https://github.com/rescuezilla/rescuezilla/issues/69))
* Removed restrictions which prevented users entering special characters in filenames and paths
* Fixed use of silver “Bluebird” theme, replacing the dull grey default used by v1.0.5/v1.0.5.1 ([#48](https://github.com/rescuezilla/rescuezilla/issues/48#issuecomment-610106113))
* Increased logging of internal commands for improved ability to track down reported bugs
* Writes the log file into destination directory (so it always persists between reboots) ([#61](https://github.com/rescuezilla/rescuezilla/issues/61))
* Improved the error message when a mount (of CIFS/SMB network share) fails
* Adds boot menu item to enter “BIOS” firmware setup [EFI-boot only]
* Replaced Redo Backup logo with new Rescuezilla logo (with “Tux” pengiun mascot) ([#62](https://github.com/rescuezilla/rescuezilla/issues/62))
* Switched ISO naming to eg, “rescuezilla-1.0.6-32bit.iso” from “redobackup-livecd-1.0.6.iso”
* Installs Rescuezilla frontend as a deb package, which increases flexibility of installation ([#13](https://github.com/rescuezilla/rescuezilla/issues/13))
* Moved scripts from tertiary File Hierarchy Standard (eg, /usr/local/sbin/rescuezilla) to secondary FHS (eg, /usr/sbin/rescuezilla) as the rationale that scripts were “developed by the system administrator of the system it is deployed on” is no longer valid when installing as a deb package
* Minimized divergence of Rescuezilla 32-bit and 64-bit package environment: (see below)
* Replaced Chromium Web Browser with Firefox to avoid Ubuntu 20.04 snap-based packaging as [snaps cannot yet](https://github.com/rescuezilla/rescuezilla/issues/63) be installed in chroot-based environments (which the Rescuezilla build uses)
* Replaced unsupported ‘leafpad’ text editor with similarly lightweight ‘mousepad’ text editor, as 'leafpad' not available on Ubuntu 20.04
* Removed ‘maximus’ auto-maximize package (as behavior replaced by OpenBox config in v1.0.5)
* Added [Patreon](https://www.patreon.com/join/rescuezilla) as a second Firefox homepage, to help achieve sustainable funding

# Rescuezilla v1.0.5.1 (2020-03-24) 

* Added support for NVMe hard drives ([#27](https://github.com/rescuezilla/rescuezilla/issues/27))
* Fixed Redo Backup’s notorious “restore succeeded but all partitions unknown” bug ([#36](https://github.com/rescuezilla/rescuezilla/issues/36))
* Fixed restoring of backups created with several [unofficial Redo Backup v1.0.4 updates](https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates)
* Fixed “stuck at text login prompt unless using Safe Mode” issue ([#25](https://github.com/rescuezilla/rescuezilla/issues/25#issuecomment-577969658))
* Added version field for SMB/CIFS network drives for connecting to older shares ([#22](https://github.com/rescuezilla/rescuezilla/issues/22))
* Added retry unmount box to fix backing up of unmountable partitions ([#16](https://github.com/rescuezilla/rescuezilla/issues/16))
* Prevented Rescuezilla using swap partitions that are present ([#37](https://github.com/rescuezilla/rescuezilla/issues/37))
* Switched drive/partition list to sort by numeric not lexical ordering (1/2/3/10, not 1/10/2/3)
* Fixed switch to multithreaded ‘pigz’ for backup compression, which was intended for v1.0.5
* Ensured French Safe Mode boots into French-language with French keymap, not into English
* Added Spanish/Español (ES-es) translation by caralu74 (¡gracias!) ([#28](https://github.com/rescuezilla/rescuezilla/issues/28))
* Ensured that every French/German/Spanish translated string gets displayed to end-users
* Fixed an issue where some French/German/Spanish characters were not being rendered correctly

# Rescuezilla v1.0.5 (2019-11-08) 

After 7 years without a release, the abandoned Redo Backup and Recovery application has been brought back
from the dead by a new maintainer. This new fork is being developed under a new name, 'Rescuezilla'.

* Upgraded base to Ubuntu 18.04 LTS (Bionic) from Ubuntu 12.04 LTS (Precise)
* Renamed project Rescuezilla but keeping ‘Redo’ for v1.0.5 (See ‘Project Announcements’ below)
* Switched to Hardware Enablement kernel for best support of new hardware (thanks OAM775!)
* Ensured official image bootable as both USB drive and CD (v1.0.4 was only bootable as a CD)
* Added SliM (Simple Login Manager) to fix boot sometimes failing to start graphical environment
* Switched to running the graphical session as unprivileged user, for improved security
* Removed deprecated gksu (graphical frontend to su/sudo), which was never necessary
* Added PolicyKit policies to provide root privileges to certain applications (via pkexec)
* Removed deprecated system-config-lvm (graphical LVM editor)
* Replaced deprecated adeskbar (start menu) with lxpanel
* Configured lxpanel to closely match adeskbar’s look-and-feel
* Added yad dialog application and a custom graphical shutdown menu
* Removed drivereset from start menu as Rescuezilla maintainer does not have a test environment
* Replaced ‘maximus’ with openbox's builtin maximize settings, toggleable per-app
* Switched to ‘pigz’ multithreaded gzip based on OAM775’s old releases (thanks!)
* Fixed SMB/FTP passwords not working with special characters (thanks Dave Kipfer!)
* Imported patches from Michal Suchanek’s git repo from 2012 and 2015, as practical
    * Added ability to restore partition to a drive smaller than the original (thanks Michal!)
    * Added ability to configure default share name via /etc/rescuezilla/share (thanks Michal!)
    * Added log file for each partition’s partclone operation (thanks Michal!)
    * Stopped printing of SMB credentials when mounting drives (thanks Michal!)
* Stopped printing of FTP credentials when mounting drives
* Removed deprecated sfdisk ‘-x’ argument used to save extended partition information
* Replaced deprecated `sfdisk -R` call with `blockdev –rereadpt`, to force reload partition info
* Writes Rescuezilla version in the backup directory to help backwards compatibility
* Writes partition information during backup so Ubuntu 18.04 partclone can correctly restore
* Moved script from `/sbin/redobackup` to `/usr/local/sbin/rescuezilla` as per File Hierarchy Standard
* Added filesystem-aware backup/restore of btrfs, exfat, f2fs filesystems
* Fixed backup/restore of ufs, vmfs, jfs, hfs, reiserfs filesystems
* Add filesystem utilities so GParted can modify btrfs, hfs+, ufs, xfs filesystems
* Added GNU ddrescue command-line data recovery tool
* Added to right-click menu a ‘change screen resolution’ function
* Added to right-click menu an ‘open terminal here’ function
* Improved HiDPI display support by setting DPI to 125, not 96
* Improved HiDPI display support by increasing size of openbox titlebars
* Added release timestamp and version information to boot menu
* Added release timestamp to the status bar of the Redo Backup perl app
* Replaced buggy lxrandr (resolution changer), with arandr (graphical screen resolution/layout)
* Removed ‘nitrogen’ wallpaper manager application
* Configured PCManFM file manager for desktop management and wallpaper display
* Added desktop icons for important applications, mounted media
* Writes all of redobackup/drivereset output to a file in a desktop directory, for easier bug reporting
* Fixed pcmanfm Tools menu “Open Current Folder in Terminal” functionality
* Removed unnecessary theme configuration: lxappearance, gtk-theme-switcher2, obconf
* Added maketext localization framework to Redo Backup script, for easier translations
* Added French/Français translation adapted from louvetch’s old release (merci!)
* Added German/Deutsch translation adapted from chcatzsf’s old release (dankeschön!)
* Appended translations to boot menu (future release will make this scalable to more languages)
* ISO image grown to ~620MB mostly due to bloated Ubuntu, Chromium and language packs

# Redo Backup and Recovery v1.0.4 (2012-11-20)

  * Base upgrade to Ubuntu 12.04 LTS (Precise)
  * Percent complete now based on part sizes rather than total number of parts
  * Windows now have titlebars to ease minimizing, maximizing and closing
  * Time is now synced to localtime (hardware clock) after boot
  * Widget theme changed to Bluebird for Gtk3 compatibility
  * Now has a helpful beep to indicate when long processes are finished
  * Added alsamixergui to enable mixer button on volume control
  * Drive reset utility can now operate on multiple drives simultaneously
  * Removed synaptic and boot-repair packages to reduce image size

# Redo Backup and Recovery v1.0.3 (2012-05-10)

  * Restore now overwrites MBR and partition table upon completion

# Redo Backup and Recovery v1.0.2 (2012-01-03)

  * Updated to latest partclone stable binaries
  * Shorten dropdown menus with an ellipsis after certain character limit
  * Ubuntu Maverick repos for updates and backports added; base upgraded
  * Chromium browser launched with user data dir specified (to run as root)
  * Show time elapsed when backup/restore operations are completed
  * Added boot-repair tool for correcting any boot issues after restore
  * Added wget utility for easily downloading files from the command line
  * Show free space on destination drive while saving a backup
  * Warn if less than 1GB free on backup destination drive
  * Show an error if any of the partitions to restore do not exist
  * Allow spaces in network shared folders

# Redo Backup and Recovery v1.0.1 (2011-08-09)

  * LVM2 support added
  * Fixed HFS+ bug that prevented the proper partclone tool from being called
  * Minor changes to boot menu
  * Safe mode boot option now prompts user to select a valid video mode

# Redo Backup and Recovery v1.0.0 (2011-07-01)

  * Added the wodim package for command-line CD burning
  * Password boxes now display hidden characters when typed in
  * Increased boot delay for machines that are slow to display it
  * Changed default boot option to load the system into RAM with "toram"
  * Changed safe video mode to use "xforcevesa nomodeset"
  * Updated the boot help text to provide info about Ubuntu boot options
  * Removed enhanced security erase option in drive reset tool for reliability

# Redo Backup and Recovery v0.9.9 (2011-06-10)

  * Added missing ntfs-3g package to allow saving backups to NTFS drives
  * Version number can be found in bottom left after booting into GUI

# Redo Backup and Recovery v0.9.8 (2011-03-10)

  * Major platform shift; building from Ubuntu rather than xPUD in the future
  * Many base features not directly related to backup/restore have changed
  * Added boot menu option to check CD media for defects
  * Added performance enhancement section to /etc/smb.conf
  * Updated fsarchiver and partclone binaries to latest stable versions
  * Boot splash screen now displays version number for easy identification

# Redo Backup and Recovery v0.9.7 (2010-09-22)

  * Added autorun.exe to help Windows users realize that a reboot is needed
  * Changed color of UI background from orange to soft blue
  * Copied VERSION and LICENSE files to root of CD-ROM for easier access

# Redo Backup and Recovery v0.9.6 (2010-08-28)

  * Fixed: Backup required scanning net before specifying a share manually
  * Fixed: Verification for drive reset can detect success or failure
  * Fixed: Missing rsync CLI dependencies have been added to the live CD image
  * Modified the bookmarks, labels and links in the UI
  * Marked wireless features as unsupported in the UI (experimental only)
  * Default boot option uses the fbdev driver in 1024x768 (16-bit) mode
  * Removed unused boot modes (e.g. command line mode)
  * Boot screen wait time reduced to 5 seconds
  * All packages moved to the "core" image file for simplicity
  * Added the grsync graphical utility for incremental file transfers
  * Added the scp tool for secure transfer of files via SSH
  * Added the very powerful gnome-disk-utility (palimpsest)
  * Added support for encrypted volumes with cryptsetup
  * Added GUI lshw-gtk tool to easily identify computer hardware components
  * Added the baobab graphical disk usage tool

# Redo Backup and Recovery v0.9.5 (2010-08-08)

  * Major speed improvements; backups and restores now 4x faster
  * Standalone gzip binary allows the compression level to be specified
  * Updated partclone to version 0.2.13
  * Added the smartmontools "smartctl" CLI for monitoring drive health
  * Back to using syslinux from the standard Ubuntu 9.10 repo version
  * Only one isolinux.cfg/syslinux.cfg file to maintain

# Redo Backup and Recovery v0.9.4 (2010-08-02)

  * New option to manually specify a shared folder or FTP server
  * Allow retry if network mount fails or bad password is provided
  * Warning: New backup naming convention allows dashes, not underscores
  * Created /opt/backup to hold backup components (instead of using /opt/core)
  * ISO CD-ROM label changed to "Redo Backup"
  * Suppress umount error messages when they aren't really errors
  * Added testdisk_static for recovering partition tables and MBRs
  * Added rsync for copying files with a progress indicator
  * Default boot option now works with any VESA-compatible video card
  * Simplified boot menu focused on hardware support instead of languages
  * Added F1 option to boot menu to display helpful options and information
  * Cancel button kills any running backup/restore processes before exiting
  * Hotplug scripts removed at boot time to stop automounting (for gparted)
  * USB installer upgraded to syslinux-3.86, forcibly writes mbr.bin to device
  * USB installer now creates FAT32 partition and filesystem instead of FAT16
  * Optionally search for network shares on demand, rather than automatically
  * Compatibility fixes and UI improvements to factory drive reset tool
  * Added reiserfsprogs, reiser4progs and mcheck for more filesystem support

# Redo Backup and Recovery v0.9.3 (2010-07-04)

  * Warning: Not interoperable with images from previous versions
  * Updated partclone to version 0.2.12
  * Save partclone error log to /partclone.log during each operation
  * Split backup images into 2GB files rather than saving one giant file
  * Added GZIP compression to reduce size of backup image
  * Backup saves first 32768 bytes rather than 512 when imaging MBR
  * Partition list saved to *.backup instead of *.redo
  * Fixed missing nmap dependencies so that local FTP servers are found
  * USB installation now detects if CD is in /dev/scd0 or /dev/sdc1
  * Stronger warning before overwriting all data to destination drive
  * Decision to abort restoration now aborts (continued either way before)
  * Abort restore if destination drive is smaller than the original
  * Do not allow partition being saved to be selected as the destination
  * Warn when restoring to the same drive the backup image is being read from
  * Minor graphic adjustment to title image
  * Removed kernel boot option "quiet" so users can see it is booting
  * Removed kernel boot option "noisapnp" (added by default in xPUD project)
  * Splash screen implemented on USB stick installations
  * Modified boot menu appearance and help text

# Redo Backup and Recovery v0.9.2 (2010-06-24)

  * Initial release
