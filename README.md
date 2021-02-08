[![Rescuezilla banner](docs/images/banner.big.png)](https://rescuezilla.com) 

# Rescuezilla [![Build Status](https://travis-ci.org/rescuezilla/rescuezilla.svg?branch=master)](https://travis-ci.org/rescuezilla/rescuezilla) 

Rescuezilla is an easy-to-use disk imaging application that's fully compatible with Clonezilla — the industry-standard trusted by tens of millions.

Disk imaging is the process of making a backup of your computer's hard drive which is managed as files stored on an external hard drive.

For many people, the alternative open-source tools Clonezilla and SysRescueCD, are intimidating and difficult to use, so Rescuezilla provides an easy-to-use graphical environment like the leading commercial tools, Acronis True Image and Macrium Reflect.

Rescuezilla can be booted on any PC or Mac from a USB stick, or CD, and has been carefully developed to be fully interoperable with the Clonezilla. This means Rescuezilla can restore backups created by Clonezilla, and backups created by Rescuezilla can be restored using Clonezilla!

Rescuezilla is an fork of _Redo Backup and Recovery_ (now called _Redo Rescue_) after it had been abandoned for 7 years.

## Features

* Simple graphical environment anyone can use
* Fully interoperable with industry-standard Clonezilla
* Ability to the access files within Clonezilla backup images (beta)
* Boots from Live CD or a USB drive on any PC or Mac
* Full system backup, bare metal recovery, partition editing, data protection, web browsing, and more
* Extra tools for hard drive partitioning, factory reset, undeleting files
* Web browser for downloading drivers, reading documentation
* File explorer for copying and editing files even if system won't boot
* Based on Ubuntu and partclone

## Supported Languages

Rescuezilla has been translated into the following languages:

* English (en-US)
* Français (fr-FR)
* Deutsch (de-DE)
* Español (es-ES)
* Português brasileiro (pt-BR)
* Polski (pl-PL)
* Italiano (it-IT)
* Ελληνικά (el-GR)
* 日本語 (ja-JP)
* Svenska (sv-SE) ([Translation complete)](https://github.com/rescuezilla/rescuezilla/issues/186))

**Rescuezilla is now officially open for translations! See [Translations HOWTO](https://github.com/rescuezilla/rescuezilla/wiki/Translations-HOWTO) to submit a translation.**

## Screenshots

<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/2.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/2.png" alt="Easy point and click interface anyone can use"></a>
<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/3.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/3.png" alt="Backups up only the used space"></a>
<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/6.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/6.png" alt="Many powerful tools available from the start button"></a>
<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/7.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/7.png"  alt="Provides browser access even if you can't log into your PC"></a>
<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/4.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/4.png" alt="Save to hard drive, network shared folder, or FTP server"></a>
<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/1.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/1.png" alt="Select video mode, check CD integrity, or test RAM at boot"></a>
<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/9.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/9.png" alt="Easily mount Clonezilla images"></a>
<a href="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/10.png"><img width=308 height=229 src="https://raw.githubusercontent.com/rescuezilla/rescuezilla.github.io/master/media/screenshots/10.png" alt="Extract individual files from Clonezilla images"></a>

## History

Below table shows an abridged history of Rescuezilla. For more information, see the [CHANGELOG](https://raw.githubusercontent.com/rescuezilla/rescuezilla/master/CHANGELOG).

| Release             | Release Date | Operating System | Notes |
| ------------------- | ---------- | ---------------- | ---------------------------------- |
| Rescuezilla 2.1.3   | 2021-01-29 | Ubuntu 20.10     | [Download page](https://github.com/rescuezilla/rescuezilla/releases/latest)
| Rescuezilla 2.1     | 2020-12-12 | Ubuntu 20.10     | Added Image Explorer (beta)
| Rescuezilla 2.0     | 2020-10-14 | Ubuntu 20.04     | Added Clonezilla support
| Rescuezilla 1.0.6   | 2020-06-17 | Ubuntu 20.04     |
| Redo Rescue 2.0.0   | 2020-06-12 | Debian 9 Stretch | Original author [resurfaces](https://sourceforge.net/p/redobackup/discussion/general/thread/d0e37c4750/) after 7.5 year absence
| Rescuezilla 1.0.5.1 | 2020-03-24 | Ubuntu 18.04.4   |
| Rescuezilla 1.0.5   | 2019-11-08 | Ubuntu 18.04.3   | Project systematically [revived](https://sourceforge.net/p/redobackup/discussion/general/thread/116063b485/?limit=25#610c) by new developer
| Unofficial updates  | Various    | Various          | Pre-Rescuezilla [updates](https://github.com/rescuezilla/rescuezilla/wiki/Bugs-in-unofficial-Redo-Backup-updates#identifying-redo-backup-versions)
| Redo Backup 1.0.4   | 2012-11-20 | Ubuntu 12.04.1   | Last release by original author for 7.5 years
| Redo Backup 0.9.8   | 2011-03-10 | Ubuntu 10.10     | Original author [deleted](https://sourceforge.net/p/redobackup/discussion/help/thread/4ea6ca31/) v0.9.2-v0.9.7
| Redo Backup 0.9.2   | 2010-06-24 | xPUD             |

## Reviews and testimonials

Please consider posting a review of Rescuezilla on the very useful website [AlternativeTo.Net](https://alternativeto.net/software/rescuezilla/reviews/). Consider giving the project a like too! :-)

## Building 

See [Building ISO image](docs/build_instructions/BUILD.ISO.IMAGE.md)

## Future development

Rescuezilla features are prioritized according to the [roadmap](https://github.com/rescuezilla/rescuezilla/wiki/Rescuezilla-Project-Roadmap). Please consider becoming a [Patreon to help fund Rescuezilla's continued development](https://www.patreon.com/join/rescuezilla)!

## Support

If you need help, start by checking the [frequently asked questions](https://rescuezilla.com/help.html), then proceed to the [Rescuezilla forum](https://sourceforge.net/p/rescuezilla/discussion/).

## Downloads

[Download the latest Rescuezilla ISO image on the GitHub Release page](https://github.com/rescuezilla/rescuezilla/releases/latest)
