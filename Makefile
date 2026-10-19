CC ?= gcc
CFLAGS ?= -O2 -std=gnu11 -Wall -Wno-unused-parameter
GTK_CFLAGS := $(shell pkg-config --cflags gtk+-3.0 fontconfig)
GTK_LIBS := $(shell pkg-config --libs gtk+-3.0 fontconfig)
LIBS = $(GTK_LIBS) -ldl -lpthread -lm
FONTBASE = https://raw.githubusercontent.com/google/fonts/main/ofl

.PHONY: all clean package check-process check-presets
all: build/optiplex-desk build/optiplex-now-backup

build:
	mkdir -p build

build/inter.ttf: | build
	curl -fsSL "$(FONTBASE)/inter/Inter%5Bopsz%2Cwght%5D.ttf" -o $@

build/limelight.ttf: | build
	curl -fsSL "$(FONTBASE)/limelight/Limelight-Regular.ttf" -o $@

build/inter.o: build/inter.ttf
	cd build && ld -r -b binary -o inter.o inter.ttf

build/limelight.o: build/limelight.ttf
	cd build && ld -r -b binary -o limelight.o limelight.ttf

build/optiplex-desk: src/main.c src/process.c src/process.h src/presets.c src/presets.h build/inter.o build/limelight.o
	$(CC) $(CFLAGS) $(GTK_CFLAGS) src/main.c src/process.c src/presets.c build/inter.o build/limelight.o -o $@ $(LIBS)

build/optiplex-now-backup: src/backup.c | build
	$(CC) $(CFLAGS) src/backup.c -o $@ -lcrypto

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
