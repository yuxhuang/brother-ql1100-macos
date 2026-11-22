CC = clang
ARCH_FLAGS ?= -arch arm64
MACOSX_DEPLOYMENT_TARGET ?= 11.0
CPPFLAGS ?=
CFLAGS ?= -O2 -Wall -Wextra -Werror -std=c11
LDFLAGS ?=
PYTHON ?= python3

.PHONY: all test clean generate check-generated
all: build/rastertoql1100
build/rastertoql1100: src/rastertoql1100.c src/media.h
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(ARCH_FLAGS) -mmacosx-version-min=$(MACOSX_DEPLOYMENT_TARGET) $< $(LDFLAGS) -lcups -o $@
generate:
	$(PYTHON) src/generate_media.py
check-generated:
	$(PYTHON) src/generate_media.py --check
test: all check-generated
	$(PYTHON) -m unittest discover -s tests -v
clean:
	rm -rf build
