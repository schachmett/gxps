#!/usr/bin/env bash
# Copyright 2016 Christoph Reiter
# modified from:
# https://github.com/quodlibet/quodlibet/blob/master/win_installer/bootstrap.sh

set -e

function main {

    if [[ "$MSYSTEM" == "MINGW32" ]]; then
        local MSYS2_ARCH="i686"
    else
        local MSYS2_ARCH="x86_64"
    fi

    pacman --noconfirm -Suy

    pacman --noconfirm -S --needed \
        git \
        base-devel \
        mingw-w64-$MSYS2_ARCH-gtk3

    pacman --noconfirm -S --needed \
        mingw-w64-$MSYS2_ARCH-python3 \
        mingw-w64-$MSYS2_ARCH-python3-numpy \
        mingw-w64-$MSYS2_ARCH-python3-matplotlib \
        mingw-w64-$MSYS2_ARCH-python3-scipy \
        mingw-w64-$MSYS2_ARCH-python3-more-itertools \
        mingw-w64-$MSYS2_ARCH-python3-gobject \
        mingw-w64-$MSYS2_ARCH-python3-cairo \
        mingw-w64-$MSYS2_ARCH-python3-pip \
        mingw-w64-$MSYS2_ARCH-python3-pytest \
        mingw-w64-$MSYS2_ARCH-python3-cairo

    /mingw64/bin/python3.8 -m pip install --user -U bidict cairocffi lmfit
}

main;
