CC ?= gcc
CFLAGS ?= -O2 -std=gnu11 -Wall -Wno-unused-parameter
LIBS = -Wl,-l:libgtk-3.so.0 -Wl,-l:libgdk-3.so.0 -Wl,-l:libgobject-2.0.so.0 -Wl,-l:libglib-2.0.so.0 -Wl,-l:libfontconfig.so.1 -Wl,-l:libgio-2.0.so.0 -ldl -lpthread -lm
FONTBASE = https://raw.githubusercontent.com/google/fonts/main/ofl

.PHONY: all clean package
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

build/optiplex-desk: src/main.c build/inter.o build/limelight.o
	$(CC) $(CFLAGS) src/main.c build/inter.o build/limelight.o -o $@ $(LIBS)

build/optiplex-now-backup: src/backup.c | build
	$(CC) $(CFLAGS) src/backup.c -o $@ -lcrypto

package: all
	python3 package.py

clean:
	rm -rf build dist
