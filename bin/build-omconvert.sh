#!/bin/bash
set -e
cd $(cd -P -- "$(dirname -- "$0")" && pwd -P)
BUILD_DIR=../../../src/omconvert
if [ ! -f "$BUILD_DIR/Makefile" ]; then
	mkdir -p omconvert.build
	curl -L https://github.com/digitalinteraction/omconvert/archive/master.zip -o omconvert.build/master.zip
	unzip -o omconvert.build/master.zip -d omconvert.build
	BUILD_DIR=omconvert.build/omconvert-master/src/omconvert
fi
make -C "$BUILD_DIR"
cp "$BUILD_DIR/omconvert" .
