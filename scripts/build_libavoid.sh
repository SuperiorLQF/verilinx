#!/bin/sh
set -eu

cd -- "$(dirname -- "$0")/.."
revision=840ebcff20dbba36ad03a2160edf7cbaf9859984
checksum=a9de2720a5781de290cf5fc064b121b62a93ae3b041dcc322a5af436eaa2af3b
runtime="$(pwd)/.runtime/libavoid"
archive="$runtime/adaptagrams.tar.gz"
source="$runtime/adaptagrams-$revision"
mkdir -p "$runtime"
if [ ! -f "$archive" ]; then
    download=$(mktemp "$runtime/adaptagrams.XXXXXX")
    trap 'rm -f -- "$download"' EXIT HUP INT TERM
    curl -fLsS --retry 2 "https://codeload.github.com/mjwybrow/adaptagrams/tar.gz/$revision" -o "$download"
    printf '%s  %s\n' "$checksum" "$download" | sha256sum -c -
    mv -- "$download" "$archive"
fi
printf '%s  %s\n' "$checksum" "$archive" | sha256sum -c -
if [ ! -f "$source/cola/libavoid/router.cpp" ]; then
    tar -xzf "$archive" -C "$runtime"
fi
cmake -S desktop/native -B "$runtime/build" -DADAPTAGRAMS_COLA="$source/cola" -DCMAKE_BUILD_TYPE=Release
cmake --build "$runtime/build" --parallel "${VERILINX_BUILD_JOBS:-4}"
