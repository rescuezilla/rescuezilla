SOURCE_DIR ?= .
PREFIX ?= /usr
DESTDIR ?=
POLKIT_ACTION_DIR ?= /usr/share/polkit-1/actions
VERSION_STRING ?= VERSION-SUBSTITUTED-BY-BUILD-SCRIPT
GIT_COMMIT_DATE ?= GIT-COMMIT-DATE-SUBSTITUTED-BY-BUILD-SCRIPT

.PHONY: msgfmt check-lfs install

msgfmt:
	for po in $(SOURCE_DIR)/usr/share/locale/*/LC_MESSAGES/$(APP_NAME).po; do \
	  msgfmt --check --output-file=/dev/null "$$po"; \
	done

check-lfs:
	@if test -d "$(SOURCE_DIR)/usr/share/rescuezilla" && \
	  grep -RIl '^version https://git-lfs.github.com/spec/v1$$' \
	  "$(SOURCE_DIR)/usr/share/rescuezilla" | grep -q .; then \
	  echo "Git LFS assets are missing; run: git lfs pull" >&2; \
	  exit 1; \
	fi

install: msgfmt check-lfs
	install -d "$(DESTDIR)$(PREFIX)" "$(DESTDIR)/etc"
	rsync -rlptD --exclude='__pycache__' --exclude='*.pyc' \
	  --exclude='share/locale/*/LC_MESSAGES/*.po' \
	  --exclude='share/polkit-1/actions/com.rescuezilla.rescuezilla.policy' \
	  "$(SOURCE_DIR)/usr/" "$(DESTDIR)$(PREFIX)/"
	if test -d "$(SOURCE_DIR)/etc"; then \
	  rsync -rlptD "$(SOURCE_DIR)/etc/" "$(DESTDIR)/etc/"; \
	fi
	if test -f "$(SOURCE_DIR)/usr/share/polkit-1/actions/com.rescuezilla.rescuezilla.policy"; then \
	  rm -f "$(DESTDIR)$(PREFIX)/share/polkit-1/actions/com.rescuezilla.rescuezilla.policy"; \
	  install -d "$(DESTDIR)$(POLKIT_ACTION_DIR)"; \
	  install -m 0644 \
	    "$(SOURCE_DIR)/usr/share/polkit-1/actions/com.rescuezilla.rescuezilla.policy" \
	    "$(DESTDIR)$(POLKIT_ACTION_DIR)/com.rescuezilla.rescuezilla.policy"; \
	fi
	for po in $(SOURCE_DIR)/usr/share/locale/*/LC_MESSAGES/$(APP_NAME).po; do \
	  relative=$${po#$(SOURCE_DIR)/usr/}; \
	  mo=$${relative%.po}.mo; \
	  install -d "$(DESTDIR)$(PREFIX)/$$(dirname "$$mo")"; \
	  msgfmt --check --output-file="$(DESTDIR)$(PREFIX)/$$mo" "$$po"; \
	done
	if test -f "$(DESTDIR)$(PREFIX)/share/applications/rescuezilla.desktop"; then \
	  sed -i 's|@PREFIX@|$(PREFIX)|g' \
	    "$(DESTDIR)$(PREFIX)/share/applications/rescuezilla.desktop" \
	    "$(DESTDIR)$(POLKIT_ACTION_DIR)/com.rescuezilla.rescuezilla.policy"; \
	  sed -i 's|VERSION-SUBSTITUTED-BY-BUILD-SCRIPT|$(VERSION_STRING)|g' \
	    "$(DESTDIR)$(PREFIX)/share/rescuezilla/VERSION"; \
	  sed -i 's|GIT-COMMIT-DATE-SUBSTITUTED-BY-BUILD-SCRIPT|$(GIT_COMMIT_DATE)|g' \
	    "$(DESTDIR)$(PREFIX)/share/rescuezilla/GIT_COMMIT_DATE"; \
	fi
