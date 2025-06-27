#!/usr/bin/python3
#
# Helper script to delete a specific translation line. Both the source English string and the translation.

# One-higher than directory containing this build script
BASEDIR="$(git rev-parse --show-toplevel)"

SEARCH_STRING="$1"

LOCALE_PATHS=(
    "src/apps/rescuezilla/rescuezilla/usr/share/locale"
    "src/livecd/image/boot/grub/locale"
)

cd $BASE_DIR

echo "Usage: ./remove-english-msgid-and-translation-msgstr.py search_string"


do_deletion() {
    file_path="$1"
    search_string="$2"

    echo "** Looking at $file_path"
    # Find line number of the first line matching the target string
    start_line=$(tail -n +0 $file_path | grep -n -m1 $search_string)

    # Find the offset between the previously found line and next translation string
    offset_line=$(tail -n +$((start_line + 1 )) $file_path | grep -n -m1 'msgid')\
    # Calculate the endline
    end_line=$(($start_line - $offset_line))
    echo "** Found $start_line to $end_line"

    # Conduct deletion
    sed "${start_line},${end_line}d" "${file_path}"
}


for base in "${LOCALE_PATHS[@]}"; do
    for file_path in ${base}/*; do
        echo "Processing $file_path"
        do_deletion "file_path" "$SEARCH_STRING"
    done
done
