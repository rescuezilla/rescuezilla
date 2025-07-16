#!/bin/bash
#
# Utility functions for Rescuezilla update scripts
#

# Create a new git branch for updates
do_git_branch() {
    local branch_name="$1"
    local remote_branch_name="$2"
    
    git checkout $remote_branch_name
    git branch -D "$branch_name"
    git submodule update --init --recursive
    git fetch origin
    git checkout $remote_branch_name -b "$branch_name"
}

# Check if a git tag exists, print warning and delete if it does
delete_local_tag_if_exists() {
    local tag_name="$1"
    
    if git tag -l | grep -q "^${tag_name}$"; then
        echo "WARNING: Tag '$tag_name' already exists. Deleting it..."
        git tag -d "$tag_name"
    fi
} 