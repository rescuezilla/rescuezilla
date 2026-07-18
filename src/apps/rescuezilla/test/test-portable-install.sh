#!/bin/sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT HUP INT TERM

make -C "$app_dir" install \
    PREFIX=/usr \
    DESTDIR="$stage" \
    VERSION_STRING=test-version \
    GIT_COMMIT_DATE=test-date

test -x "$stage/usr/bin/rescuezilla"
test -x "$stage/usr/bin/rescuezillapy"
test -x "$stage/usr/lib/rescuezilla/rescuezilla.py"
test -s "$stage/usr/share/rescuezilla/rescuezilla.glade"
test -s "$stage/usr/share/locale/hu/LC_MESSAGES/rescuezilla.mo"
test ! -e "$stage/usr/sbin"
test ! -e "$stage/usr/lib/python3/dist-packages"
sh -n "$stage/usr/bin/rescuezilla"
grep -qx 'Exec=/usr/bin/rescuezilla' \
    "$stage/usr/share/applications/rescuezilla.desktop"
grep -q '>/usr/bin/rescuezilla<' \
    "$stage/usr/share/polkit-1/actions/com.rescuezilla.rescuezilla.policy"
! grep -R -E '/usr/sbin/rescuezilla|dist-packages|/run/user/999|su ubuntu' \
    "$stage/usr/bin" "$stage/usr/lib/rescuezilla" \
    "$stage/usr/share/applications" "$stage/usr/share/polkit-1/actions" || exit 1

fake_bin="$stage/fake-bin"
arg_log="$stage/actual-args"
expected_args="$stage/expected-args"
mkdir -p "$fake_bin"

for command in flock python3 pkexec; do
    printf '%s\n' '#!/bin/sh' 'printf "%s\n" "$@" > "$ARG_LOG"' \
        > "$fake_bin/$command"
    chmod +x "$fake_bin/$command"
done
printf '%s\n' '#!/bin/sh' 'printf "%s\n" "${FAKE_UID:-1000}"' \
    > "$fake_bin/id"
printf '%s\n' '#!/bin/sh' 'exit 1' > "$fake_bin/pgrep"
chmod +x "$fake_bin/id" "$fake_bin/pgrep"

# Keep the production launcher PATH fixed; only the staged test copy is
# redirected so its external commands are deterministic.
sed -i "s|^PATH=.*|PATH=$fake_bin:/usr/bin:/bin|" \
    "$stage/usr/bin/rescuezilla"
printf '%s\n' "$stage/usr/bin/rescuezilla" 'two words' '--flag' \
    > "$expected_args"
ARG_LOG="$arg_log" FAKE_UID=1000 \
    "$stage/usr/bin/rescuezilla" 'two words' --flag
cmp "$expected_args" "$arg_log"
