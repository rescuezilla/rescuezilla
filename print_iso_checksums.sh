#!/bin/bash

SHA256=$(sha256sum "$1")
SHA1=$(sha1sum "$1")
MD5=$(md5sum "$1")

printf "sha256sum:\n$SHA256\n\n"
printf "sha1sum:\n$SHA1\n\n"
printf "md5sum:\n$MD5\n\n"
