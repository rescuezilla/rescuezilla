# Installing Rescuezilla from source

These commands install the build tools and core GTK application dependencies.

## Debian / Ubuntu

```bash
sudo apt install git git-lfs make gettext rsync python3 python3-gi \
  python3-cairo gir1.2-gtk-3.0 pkexec procps util-linux xdg-utils
```

## Fedora / RHEL family

```bash
sudo dnf install git git-lfs make gettext rsync python3 python3-gobject \
  python3-cairo gtk3 polkit procps-ng util-linux xdg-utils
```

## openSUSE

```bash
sudo zypper install git git-lfs make gettext-tools rsync python3 \
  python3-gobject-Gdk python3-pycairo typelib-1_0-Gtk-3_0 polkit \
  procps util-linux xdg-utils
```

Zypper resolves these generic capabilities to the distribution's current default versioned Python RPMs.

## Arch / CachyOS

```bash
sudo pacman -S --needed git git-lfs make gettext rsync python python-gobject \
  python-cairo gtk3 polkit procps-ng util-linux xdg-utils
```

Fetch the Git LFS assets after cloning the repository:

```bash
git lfs pull
```

To inspect the install without changing the host, stage it in a temporary directory:

```bash
stage=$(mktemp -d)
make -C src/apps/rescuezilla install PREFIX=/usr DESTDIR="$stage"
```

Install and launch Rescuezilla with:

```bash
sudo make -C src/apps/rescuezilla install PREFIX=/usr/local
/usr/local/bin/rescuezilla
```

RPM and PKGBUILD maintainers should wrap the same `make install` target with the package manager's staging directory.

## Optional capabilities

The package commands above are enough to launch the core UI. Backup, restore, and clone operations additionally need the tools for the operation and image format being used, such as Partclone, Clonezilla, FSArchiver, QEMU image tools, compressors, network clients, and filesystem utilities.

Image Explorer needs an `nbd-client`; `nbdkit` with split, file, truncate, and the required compression support; `partclone-nbd` for Partclone images; `qemu-nbd` and `qemu-img` for virtual-machine images; and filesystem drivers for the filesystems being mounted. These are capability requirements, not universal package names: availability and package splits vary by distribution.
