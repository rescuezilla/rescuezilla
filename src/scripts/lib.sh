#
# Common helper functions
#

PRIMARY_URL="${PRIMARY_URL:-http://archive.ubuntu.com/ubuntu}"
PORTS_URL="${PORTS_URL:-http://ports.ubuntu.com/ubuntu-ports/ubuntu-ports}"

# Returns the HTTP status code for a URL without downloading the body.
# $1: URL to check
function get_url_http_status() {
  local url="${1}"
  curl --head --silent --output /dev/null --write-out "%{http_code}" "$url"
}

# Determine if we can use the primary mirror or need to use the "old-releases" mirror.
# Because every 6 months (for non-LTS releases) [1], the releases are moved from the primary
# mirror to the old-releases mirror. To keep the build working we must use the
# old-releases mirror when this happens.
#
# The intent is not to create new releases based on end-of-life versions, but to be able to
# add releases without immediately deprecating old ones.
#
# [1] https://endoflife.date/ubuntu
#
# Sets the URL variable in the calling scope.
# Reads CODENAME and ARCH variables from the calling scope.
function identify_sources_url_old_release_or_port() {
  if [ "$CODENAME" = "INVALID" ] || [ "$ARCH" = "INVALID" ]; then
    echo "The variable CODENAME=${CODENAME} or ARCH=${ARCH} was not set correctly. Are you using the Makefile? Please consult build instructions."
    exit 1
  elif [ "$ARCH" = "amd64" ] || [ "$ARCH" = "i386" ]; then
    echo "Setting URL to main mirror"
    URL="$PRIMARY_URL"
  else
    echo "Setting URL to ports mirror"
    URL="$PORTS_URL"
  fi

  # The file named "Release" on the remote server is small, and sufficient to determine if the path is valid
  local release_file_path="dists/$CODENAME/Release"
  local http_status
  # Try the primary mirror first
  http_status=$(get_url_http_status "$URL/$release_file_path")
  echo "HTTP status for $URL/$release_file_path: $http_status"
  if [ "$http_status" = "404" ]; then
    # If the primary mirror 404'd, try the old-releases mirror
    local old_releases_url="https://old-releases.ubuntu.com/ubuntu"
    echo "URL returned 404. Trying old-releases mirror: $old_releases_url/$release_file_path"
    http_status=$(get_url_http_status "$old_releases_url/$release_file_path")
    echo "HTTP status for $old_releases_url/$release_file_path: $http_status"
    # Hopefully at least the old-releases mirror succeeded!
    if [ "$http_status" != "200" ]; then
      echo "Error: old-releases mirror returned HTTP $http_status for $CODENAME. Cannot determine apt sources URL."
      exit 1
    fi
    echo "Setting URL to old-releases mirror"
    URL="$old_releases_url"
  fi
}

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

