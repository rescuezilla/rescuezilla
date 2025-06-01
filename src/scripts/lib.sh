#
# Common helper functions
#

# Check dependency exists 
#
# $1: command to test
#
function exit_if_missing_command() {
    COMMAND="${1}"
    if ! command -v $COMMAND 2>&1 >/dev/null
    then
       echo "Missing command ${COMMAND}. Please confirm it's installed. Exiting."
       exit 1
    fi
}

