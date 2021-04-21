#!/bin/bash
set -e
cd $(cd -P -- "$(dirname -- "$0")" && pwd -P)
BUILD_DIR=omconvert.build
mkdir -p $BUILD_DIR
curl -L https://github.com/digitalinteraction/omconvert/archive/master.zip -o $BUILD_DIR/master.zip
unzip -o $BUILD_DIR/master.zip -d $BUILD_DIR
make -C "$BUILD_DIR/omconvert-master/src/omconvert"
cp "$BUILD_DIR/omconvert-master/src/omconvert/omconvert" .
