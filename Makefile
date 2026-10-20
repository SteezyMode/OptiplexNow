CC ?= gcc
CFLAGS ?= -O2 -std=gnu11 -Wall -Wno-unused-parameter -Werror=incompatible-pointer-types -Werror=implicit-function-declaration
GTK_CFLAGS := $(shell pkg-config --cflags gtk+-3.0 fontconfig)
GTK_LIBS := $(shell pkg-config --libs gtk+-3.0 fontconfig)
LIBS = $(GTK_LIBS) -ldl -lpthread -lm
FONT_REV = 47d54ca1ebb14fd864695f1d39dc734f39017c33
INTER_BLOB = 047c92f6e2212473dc436020afed689527076d44
LIMELIGHT_BLOB = 879e7f9d7a6240defbc5ecf97cd819905ef0c242
FONTBASE = https://raw.githubusercontent.com/google/fonts/$(FONT_REV)/ofl

.PHONY: all clean package check-process check-presets check-config check-wolf-pairing check-wolf-transport
all: build/optiplex-desk build/optiplex-now-backup

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

build/optiplex-desk: src/main.c src/process.c src/process.h src/presets.c src/presets.h src/config.c src/config.h src/wolf_pairing.c src/wolf_pairing.h src/wolf_transport.c src/wolf_transport.h build/inter.o build/limelight.o
	$(CC) $(CFLAGS) $(GTK_CFLAGS) src/main.c src/process.c src/presets.c src/config.c src/wolf_pairing.c src/wolf_transport.c build/inter.o build/limelight.o -o $@ -Wl,-z,noexecstack $(LIBS)

build/optiplex-now-backup: src/backup.c | build
	$(CC) $(CFLAGS) -Werror=misleading-indentation -Werror=parentheses src/backup.c -o $@ -lcrypto

package: all
	python3 package.py

clean:
	rm -rf build dist

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
