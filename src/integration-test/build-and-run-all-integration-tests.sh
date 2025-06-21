#!/bin/bash
#
set -x

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
BASEDIR="$(git rev-parse --show-toplevel)"

cd "$BASEDIR"

# TODO: get rid of this
sudo make clean

# Create Docker container
make docker-build
make docker-run

# Make 
IS_INTEGRATION_TEST=true make docker-bionic-i386
IS_INTEGRATION_TEST=true make docker-focal
IS_INTEGRATION_TEST=true make docker-jammy
IS_INTEGRATION_TEST=true make docker-oracular

src/integration-test/integration_test.py reset
src/integration-test/integration_test.py deploy

src/integration-test/run-all.sh



