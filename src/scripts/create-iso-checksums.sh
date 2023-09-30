#!/bin/bash

# Echo each command
set -x

sha256sum "$@" | tee SHA256SUM
sha1sum "$@" | tee SHA1SUM
md5sum "$@" | tee MD5SUM
