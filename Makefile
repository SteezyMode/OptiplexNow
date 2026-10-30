CC ?= gcc
CFLAGS ?= -O2 -std=gnu11 -Wall -Wno-unused-parameter -Werror=incompatible-pointer-types -Werror=implicit-function-declaration
GTK_CFLAGS := $(shell pkg-config --cflags gtk+-3.0 fontconfig)
GTK_LIBS := $(shell pkg-config --libs gtk+-3.0 fontconfig)
LIBS = $(GTK_LIBS) -ldl -lpthread -lm
FONT_REV = 47d54ca1ebb14fd864695f1d39dc734f39017c33
INTER_BLOB = 047c92f6e2212473dc436020afed689527076d44
LIMELIGHT_BLOB = 879e7f9d7a6240defbc5ecf97cd819905ef0c242
FONTBASE = https://raw.githubusercontent.com/google/fonts/$(FONT_REV)/ofl

.PHONY: all clean package check-ui-wizard check-ui-settings check-settings-persistence check-instance-lock check-process check-presets check-config check-wolf-pairing check-wolf-transport check-games-flow check-media-endpoint-token check-tailscale check-host-metrics check-host-job-target check-backup-async check-tray-prefs check-tray-actions check-desktop-autostart check-moonlight-install check-wizard-network check-wizard-services check-service-probe check-sanitizers
all: build/optiplex-desk build/optiplex-now-backup build/now-ssh-askpass build/now-host-setup

build:
	mkdir -p build

# Pin exact upstream font source and never leave a partial successful target.
# Re-fetch when Makefile changes, so an existing build directory cannot silently
# retain the old unpinned fonts after upgrading this build system.
build/inter.ttf: Makefile | build
	@set -eu; tmp="$@.part"; trap 'rm -f "$$tmp"' EXIT; \
	curl -fsSL --retry 3 --connect-timeout 10 --max-time 90 "$(FONTBASE)/inter/Inter%5Bopsz%2Cwght%5D.ttf" -o "$$tmp"; \
	python3 tools/verify_font.py "$$tmp" $(INTER_BLOB) 876576; mv "$$tmp" "$@"; trap - EXIT

build/limelight.ttf: Makefile | build
	@set -eu; tmp="$@.part"; trap 'rm -f "$$tmp"' EXIT; \
	curl -fsSL --retry 3 --connect-timeout 10 --max-time 90 "$(FONTBASE)/limelight/Limelight-Regular.ttf" -o "$$tmp"; \
	python3 tools/verify_font.py "$$tmp" $(LIMELIGHT_BLOB) 132292; mv "$$tmp" "$@"; trap - EXIT

build/inter.o: build/inter.ttf
	cd build && ld -r -b binary -o inter.o inter.ttf

build/limelight.o: build/limelight.ttf
	cd build && ld -r -b binary -o limelight.o limelight.ttf

build/optiplex-desk: src/main.c src/instance_lock.c src/instance_lock.h src/process.c src/process.h src/presets.c src/presets.h src/config.c src/config.h src/wolf_pairing.c src/wolf_pairing.h src/wolf_transport.c src/wolf_transport.h src/games_flow.c src/games_flow.h src/media_flow.c src/media_flow.h src/media_endpoint_token.c src/media_endpoint_token.h src/downloads_flow.c src/downloads_flow.h src/downloads_queue_view.c src/downloads_queue_view.h src/downloads_search_view.c src/downloads_search_view.h src/downloads_destination_view.c src/downloads_destination_view.h src/downloads_webview.c src/downloads_webview.h src/ui_navigation.c src/ui_navigation.h src/ui_games.c src/ui_settings.c src/ui_wizard.c src/settings_persistence.c src/ui_games.h src/ui_settings.h src/ui_wizard.h src/settings_persistence.h src/ui_state.c src/ui_state.h src/desktop_autostart.c src/desktop_autostart.h src/tailscale_async.c src/tailscale_async.h src/tailscale_install.c src/tailscale_install.h src/ssh_authorize.c src/ssh_authorize.h src/host_metrics.c src/host_metrics.h src/host_job_target.c src/host_job_target.h src/backup_async.c src/backup_async.h src/tray_prefs.c src/tray_prefs.h src/tray_actions.c src/tray_actions.h src/moonlight_install.c src/moonlight_install.h src/wizard_network.c src/wizard_network.h src/service_probe.c src/service_probe.h src/wizard_services.c src/wizard_services.h build/inter.o build/limelight.o
	$(CC) $(CFLAGS) $(GTK_CFLAGS) src/main.c src/instance_lock.c src/process.c src/presets.c src/config.c src/wolf_pairing.c src/wolf_transport.c src/games_flow.c src/media_flow.c src/media_endpoint_token.c src/downloads_flow.c src/downloads_queue_view.c src/downloads_search_view.c src/downloads_destination_view.c src/downloads_webview.c src/ui_navigation.c src/ui_games.c src/ui_settings.c src/ui_wizard.c src/settings_persistence.c src/ui_state.c src/desktop_autostart.c src/tailscale_async.c src/tailscale_install.c src/ssh_authorize.c src/host_metrics.c src/host_job_target.c src/backup_async.c src/tray_prefs.c src/tray_actions.c src/moonlight_install.c src/wizard_network.c src/service_probe.c src/wizard_services.c build/inter.o build/limelight.o -o $@ -Wl,-z,noexecstack $(LIBS)

# Separate native server readiness window. No privileged operations.
build/now-host-setup: src/host_setup.c | build
	$(CC) $(CFLAGS) $(GTK_CFLAGS) src/host_setup.c -o $@ $(GTK_LIBS)

build/optiplex-now-backup: src/backup.c | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Werror=parentheses src/backup.c -o $@ -lcrypto

package: all
	python3 package.py

clean:
	rm -rf build dist

# Single-instance process behavior without GTK, host services or network.
check-instance-lock: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_instance_lock.c src/instance_lock.c -o build/test-instance-lock
	./build/test-instance-lock

# Fast standalone regression check; does not require a running GTK desktop.
check-process: | build
	$(CC) $(CFLAGS) -Isrc tests/test_process.c src/process.c -o build/test-process
	./build/test-process

# Round-trip and backwards-compatibility checks for portable client presets.
check-presets: | build
	$(CC) $(CFLAGS) -Isrc tests/test_presets.c src/presets.c -o build/test-presets
	./build/test-presets

# Behavior tests for configuration compatibility; no GUI or private files required.
check-config: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_config.c src/config.c -o build/test-config
	./build/test-config

# Compile the pairing parser and payload validator without a GTK display or SSH host.
check-wolf-pairing: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_wolf_pairing.c src/wolf_pairing.c -o build/test-wolf-pairing
	./build/test-wolf-pairing

# Exercise the async subprocess boundary without a GTK display or real SSH host.
check-wolf-transport: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_wolf_transport.c src/wolf_transport.c -o build/test-wolf-transport $(shell pkg-config --libs gio-2.0)
	./build/test-wolf-transport

# Restricted per-device Games helper: GTK-free async transport and state parser.
check-games-flow: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_games_flow.c src/games_flow.c -o build/test-games-flow $(shell pkg-config --libs gio-2.0)
	./build/test-games-flow

# Only fixed, validated same-host media endpoint tokens reach GTK.
check-media-endpoint-token: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags glib-2.0) tests/test_media_endpoint_token.c src/media_endpoint_token.c -o build/test-media-endpoint-token $(shell pkg-config --libs glib-2.0)
	./build/test-media-endpoint-token

# Exercise the isolated Tailscale helper transport and discovery parser.
check-tailscale: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_tailscale_async.c src/tailscale_async.c -o build/test-tailscale $(shell pkg-config --libs gio-2.0)
	./build/test-tailscale

# Parse host telemetry without a server, Docker, or GTK session.
check-host-metrics: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_host_metrics.c src/host_metrics.c -o build/test-host-metrics
	./build/test-host-metrics

# Immutable SSH target snapshots and stale-result detection without GTK.
check-host-job-target: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_host_job_target.c src/host_job_target.c -o build/test-host-job-target
	./build/test-host-job-target

# Real asynchronous backup bridge with a disposable, non-privileged helper.
check-backup-async: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_backup_async.c src/backup_async.c -o build/test-backup-async $(shell pkg-config --libs gio-2.0)
	./build/test-backup-async

# GTK-free tray preferences: legacy paths, action order, masks and safe saving.
check-tray-prefs: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_tray_prefs.c src/tray_prefs.c -o build/test-tray-prefs
	./build/test-tray-prefs

# Test tray routing without GTK widgets, side effects or a real host.
check-tray-actions: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_tray_actions.c src/tray_actions.c -o build/test-tray-actions
	./build/test-tray-actions

# XDG per-user login startup: no real desktop session, root or host touched.
check-desktop-autostart: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_desktop_autostart.c src/desktop_autostart.c -o build/test-desktop-autostart $(shell pkg-config --libs gio-2.0)
	./build/test-desktop-autostart

# Use a disposable fake flatpak binary; no root or network required.
check-moonlight-install: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_moonlight_install.c src/moonlight_install.c -o build/test-moonlight-install $(shell pkg-config --libs gio-2.0)
	./build/test-moonlight-install

# Wizard request lifecycle: two independent jobs, timeout/retry, and closed UI.
check-wizard-network: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_wizard_network.c src/wizard_network.c src/tailscale_async.c -o build/test-wizard-network $(shell pkg-config --libs gio-2.0)
	./build/test-wizard-network

# Wizard URLs: validate together, persist and reload without a live server.
check-wizard-services: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc tests/test_wizard_services.c src/wizard_services.c src/presets.c src/config.c -o build/test-wizard-services
	./build/test-wizard-services

# Disposable curl command fixture; no external HTTP or GTK session.
check-service-probe: | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_service_probe.c src/service_probe.c src/presets.c -o build/test-service-probe $(shell pkg-config --libs gio-2.0)
	./build/test-service-probe

# The GTK askpass program is a separate graphical process used by OpenSSH.
build/now-ssh-askpass: src/ssh_askpass.c | build
	$(CC) $(CFLAGS) $(GTK_CFLAGS) src/ssh_askpass.c -o $@ $(GTK_LIBS)


# Independent native-code diagnostics. Never used for the published .deb.
# Leak detection is disabled for GIO/GTK process-global allocations; ASan
# bounds/use-after-free and UBSan checks remain active.
SAN_CFLAGS = -std=gnu11 -O1 -g -Wall -Wextra -Werror=implicit-function-declaration -Werror=incompatible-pointer-types -Werror=return-type -Werror=format-security -Wformat=2 -Werror=misleading-indentation -fno-omit-frame-pointer -fsanitize=address,undefined
SAN_LIBS = -fsanitize=address,undefined
SAN_ENV = ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1

# Compiled behavioral tests run through AddressSanitizer + UBSan. No fonts,
# server, network, live credentials, or graphical session are needed.
# Isolated four-page first-run GTK view: no network, host or device identity.
check-ui-wizard: | build
	$(CC) $(CFLAGS) $(GTK_CFLAGS) -Isrc tests/test_ui_wizard.c src/ui_wizard.c -o build/test-ui-wizard $(GTK_LIBS)
	xvfb-run -a ./build/test-ui-wizard

# Standalone GTK presentation behavior, no app shell or host/service access.
# No GTK widgets or host services: isolated real local preferences.
check-settings-persistence: | build
	$(CC) $(CFLAGS) -Isrc $(shell pkg-config --cflags glib-2.0) tests/test_settings_persistence.c src/settings_persistence.c src/desktop_autostart.c src/tray_prefs.c src/ui_state.c src/host_metrics.c src/presets.c -o build/test-settings-persistence $(shell pkg-config --libs glib-2.0)
	./build/test-settings-persistence

check-ui-settings: | build
	$(CC) $(CFLAGS) $(GTK_CFLAGS) -Isrc tests/test_ui_settings.c src/ui_settings.c src/ui_navigation.c src/config.c src/tray_prefs.c src/ui_state.c src/desktop_autostart.c -o build/test-ui-settings $(GTK_LIBS)
	xvfb-run -a ./build/test-ui-settings
check-sanitizers: | build
	mkdir -p build/sanitized
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_instance_lock.c src/instance_lock.c -o build/sanitized/test-instance-lock $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-instance-lock
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_process.c src/process.c -o build/sanitized/test-process $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-process
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_presets.c src/presets.c -o build/sanitized/test-presets $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-presets
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_config.c src/config.c -o build/sanitized/test-config $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-config
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_wizard_services.c src/wizard_services.c src/presets.c src/config.c -o build/sanitized/test-wizard-services $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-wizard-services
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_wolf_pairing.c src/wolf_pairing.c -o build/sanitized/test-wolf-pairing $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-wolf-pairing
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_host_metrics.c src/host_metrics.c -o build/sanitized/test-host-metrics $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-host-metrics
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_host_job_target.c src/host_job_target.c -o build/sanitized/test-host-job-target $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-host-job-target
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_backup_async.c src/backup_async.c -o build/sanitized/test-backup-async $(shell pkg-config --libs gio-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-backup-async
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_tray_prefs.c src/tray_prefs.c -o build/sanitized/test-tray-prefs $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-tray-prefs
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags glib-2.0) tests/test_settings_persistence.c src/settings_persistence.c src/desktop_autostart.c src/tray_prefs.c src/ui_state.c src/host_metrics.c src/presets.c -o build/sanitized/test-settings-persistence $(shell pkg-config --libs glib-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-settings-persistence
	$(CC) $(SAN_CFLAGS) -Isrc tests/test_tray_actions.c src/tray_actions.c -o build/sanitized/test-tray-actions $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-tray-actions
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_moonlight_install.c src/moonlight_install.c -o build/sanitized/test-moonlight-install $(shell pkg-config --libs gio-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-moonlight-install
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_wizard_network.c src/wizard_network.c src/tailscale_async.c -o build/sanitized/test-wizard-network $(shell pkg-config --libs gio-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-wizard-network
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_service_probe.c src/service_probe.c src/presets.c -o build/sanitized/test-service-probe $(shell pkg-config --libs gio-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-service-probe
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_wolf_transport.c src/wolf_transport.c -o build/sanitized/test-wolf-transport $(shell pkg-config --libs gio-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-wolf-transport
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_games_flow.c src/games_flow.c -o build/sanitized/test-games-flow $(shell pkg-config --libs gio-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-games-flow
	$(CC) $(SAN_CFLAGS) -Isrc $(shell pkg-config --cflags gio-2.0) tests/test_tailscale_async.c src/tailscale_async.c -o build/sanitized/test-tailscale $(shell pkg-config --libs gio-2.0) $(SAN_LIBS)
	$(SAN_ENV) ./build/sanitized/test-tailscale

# Compile-only, stricter diagnostics on extracted production modules, including
# GUI authorization helpers. The legacy main.c is deliberately excluded until
# it is split into independently testable responsibilities.
	$(CC) $(SAN_CFLAGS) $(GTK_CFLAGS) -Isrc -c src/ssh_authorize.c -o build/sanitized/ssh_authorize.o
	$(CC) $(SAN_CFLAGS) $(GTK_CFLAGS) -Isrc -c src/tailscale_install.c -o build/sanitized/tailscale_install.o
	$(CC) $(SAN_CFLAGS) $(GTK_CFLAGS) -Isrc -c src/ssh_askpass.c -o build/sanitized/ssh_askpass.o
