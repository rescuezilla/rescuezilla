.DEFAULT_GOAL := msgfmt
.PHONY: msgfmt

# This Makefile is common to all applications in the Rescuezilla suite.
#
# It is intended to be executed *by the dpkg-buildpackage function*.
# The msgfmt target modifies the source tree.
# The install target uses an environment variable set by dpkg-buildpackage.

msgfmt:
	$(info * Convert *.po text-based GTK translations into *.mo.)
	for dir in ./usr/share/locale/*/LC_MESSAGES/; do \
	  echo "Converting language translation file: $$dir/$(APP_NAME).po" && \
	  msgfmt --output-file="$$dir/$(APP_NAME).mo" "$$dir/$(APP_NAME).po" \
            || (echo "Error: Unable to convert $$dir translation from text-based \
                      po format to binary mo format: $$?"; exit 1); \
	  rm $$dir/$(APP_NAME).po ; \
	done

install:
	rsync --archive --exclude "Makefile" --exclude "debian/" "./" "$$DESTDIR"

