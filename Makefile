# krkrz_gdk: tools/krkrz_gdk.py の薄いラッパー
#
#   make [PROJECT_DIR=/path/to/game] [TARGET=desktop|scarlett|xboxone] [CONFIG=Release|Debug] <target>
#
# CMAKEOPT='-D...' で cmake configure に追加オプションを渡せる。

BUILD_SYSTEM_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
PROJECT_DIR ?= $(BUILD_SYSTEM_DIR)
TARGET ?= desktop
CONFIG ?= Release
PYTHON ?= python

export PROJECT_DIR CMAKEOPT

TOOL = $(PYTHON) "$(BUILD_SYSTEM_DIR)/tools/krkrz_gdk.py" --project "$(PROJECT_DIR)" --target $(TARGET) --config $(CONFIG)

.PHONY: all gen configure build stage package run register deploy launch vars clean

all:
	$(TOOL) all

gen configure build stage package run register deploy launch vars:
	$(TOOL) $@

clean:
	$(PYTHON) -c "import shutil,sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" "$(PROJECT_DIR)/build/gdk/$(TARGET)"
