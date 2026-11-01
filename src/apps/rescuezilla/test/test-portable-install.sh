#!/bin/sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
live_launcher="$app_dir/../../scripts/live-rescuezilla"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT HUP INT TERM

grep -Fqx 'BASE_CMD="/usr/bin/rescuezillapy $*"' "$live_launcher"
grep -Fq 'ps -e | grep rescuezillapy' "$live_launcher"

make -C "$app_dir" install \
    PREFIX=/usr/local \
    DESTDIR="$stage" \
    VERSION_STRING=test-version \
    GIT_COMMIT_DATE=test-date

test -x "$stage/usr/local/bin/rescuezilla"
test -x "$stage/usr/local/bin/rescuezillapy"
test -x "$stage/usr/local/lib/rescuezilla/rescuezilla.py"
test -s "$stage/usr/local/share/rescuezilla/rescuezilla.glade"
test -s "$stage/usr/local/share/locale/hu/LC_MESSAGES/rescuezilla.mo"
test ! -e "$stage/usr/local/sbin"
test ! -e "$stage/usr/local/lib/python3/dist-packages"
sh -n "$stage/usr/local/bin/rescuezilla"
grep -qx 'Exec=/usr/local/bin/rescuezilla' \
    "$stage/usr/local/share/applications/rescuezilla.desktop"
grep -q '>/usr/local/bin/rescuezilla<' \
    "$stage/usr/share/polkit-1/actions/com.rescuezilla.rescuezilla.policy"
test ! -e \
    "$stage/usr/local/share/polkit-1/actions/com.rescuezilla.rescuezilla.policy"
! grep -R -E '/usr/sbin/rescuezilla|dist-packages|/run/user/999|su ubuntu' \
    "$stage/usr/local/bin" "$stage/usr/local/lib/rescuezilla" \
    "$stage/usr/local/share/applications" \
    "$stage/usr/share/polkit-1/actions" || exit 1

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
    "$stage/usr/local/bin/rescuezilla"
printf '%s\n' "$stage/usr/local/bin/rescuezilla" 'two words' '--flag' \
    > "$expected_args"
ARG_LOG="$arg_log" FAKE_UID=1000 \
    "$stage/usr/local/bin/rescuezilla" 'two words' --flag
cmp "$expected_args" "$arg_log"
