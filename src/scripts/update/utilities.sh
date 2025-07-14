#!/bin/bash
#
# Utility functions for Rescuezilla update scripts
#

# Create a new git branch for updates
do_git_branch() {
    local branch_name="$1"

    git checkout origin/master
    git branch -D "$branch_name"
    git submodule update --init --recursive
    git fetch origin
    git checkout origin/master -b "$branch_name"
} 