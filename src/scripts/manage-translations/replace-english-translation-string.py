#!/usr/bin/python3
#
# Helper script to replace the original English lines across all translation files, with special care
# taken to escape the less-than/greater-than symbols used in the Glade GTKBuilder file
#
# This is useful when making slight rewording the English language text, including changing the markup
# of certain words to eg, bold or italicize them.

import glob
import subprocess
import re
import os
import sys

if len(sys.argv) < 3:
	raise Exception("Usage: ./replace_english_translation_string.py search_string replace_string")
	sys.exit(1)

git_process = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, encoding='utf-8')
if git_process.returncode != 0:
	print("Failed: " + git_process.stderr)
	sys.exit(1)
git_root = git_process.stdout
print("Using git_root: " + git_root)
language_glob = os.path.join(git_root.strip(), "src/apps/rescuezilla/rescuezilla/usr/share/locale/*")
print("Using glob: " + language_glob)

search_str = sys.argv[1]
replace_str = sys.argv[2]

# Escape the less than and greater than symbols as that what Glade requires
escaped_search_str = re.sub(">", "\\&gt;", re.sub("<", "\\&lt;", search_str))
escaped_replace_str = re.sub(">", "\\&gt;", re.sub("<", "\\&lt;", replace_str))

print("escaped_replace_str is " + escaped_replace_str)
subprocess.run(["sed", "-i", "s*" + escaped_search_str + "*" + escaped_replace_str +  "*g", "src/apps/rescuezilla/rescuezilla/usr/share/rescuezilla/rescuezilla.glade"], capture_output=True)

language_glob = os.path.join(git_root.strip(), "src/apps/rescuezilla/rescuezilla/usr/share/locale/*")
print("Using glob: " + language_glob)

language_dir_list = glob.glob(language_glob)
for language_dir in language_dir_list:
	print("Looking at " + language_dir)
	language_file = os.path.join(language_dir, "LC_MESSAGES/rescuezilla.ko")
	subprocess.run(["sed", "-i", "s*" + search_str + "*" + replace_str +  "*g", language_file], capture_output=True)

