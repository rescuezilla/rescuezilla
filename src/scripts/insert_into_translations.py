#!/usr/bin/python3
#
# Helper script to insert a user-specified file into all existing Rescuezilla translation files
# above a given regex match.
#
# This is useful as when new features are added to Rescuezilla each translation file should be
# updated with template lines, such as the following:
#
# > msgid "My first newline"
# > msgstr ""
# >
# > msgid "My second newline"
# > msgstr ""
# >
#

import glob
import os
import sys
import subprocess

if len(sys.argv) < 3:
	print("Usage: ./insert_into_translations.py search_string file_to_input")
	sys.exit(1)

git_process = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, encoding='utf-8')
if git_process.returncode != 0:
	print("Failed: " + git_process.stderr)
	sys.exit(1)
git_root = git_process.stdout
print("Using git_root: " + git_root)
language_glob = os.path.join(git_root.strip(), "src/apps/rescuezilla/rescuezilla/usr/share/locale/*")
print("Using glob: " + language_glob)

language_dir_list = glob.glob(language_glob)
for language_dir in language_dir_list:
	language_file = os.path.join(language_dir, "LC_MESSAGES/rescuezilla.po")
	print("Looking at " + language_dir)
	search_str = sys.argv[1]
	input_file = sys.argv[2]
	subprocess.run(["sed", "-i", "/" + search_str + "/e cat " + input_file, language_file], capture_output=True)
