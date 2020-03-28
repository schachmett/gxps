#!/usr/bin/env bash
# This windows building routine was largely adopted from the
# Quod Libet project
# https://github.com/quodlibet/quodlibet (C) 2016 Christoph Reiter
# and the Python GTK3 GStreamer SDK
# https://github.com/exaile/python-gtk3-gst-sdk (C) 2015 Dustin Spicuzza


function catch_sigint {
    echo "Caught kill signal, exiting..."
    exit 1
}

trap catch_sigint SIGINT;

set -e

BASEDIR=$(pwd)

# CONFIG START

ARCH="x86_64"
BUILD_VERSION="0"
GXPS_VERSION="0.0.0"
GXPS_VERSION_DESC="UNKOWN"

# CONFIG END

if [ "${ARCH}" = "x86_64" ]; then
    MINGW="mingw64"
else
    MINGW="mingw32"
fi

function set_build_root {
    BUILD_ROOT="$1"
    REPO_CLONE="${BUILD_ROOT}/gxps"
    MINGW_ROOT="${BUILD_ROOT}/${MINGW}"
    export PATH="${MINGW_ROOT}/bin:${PATH}"
}

function create_root {
    mkdir -p "${BUILD_ROOT}"

    mkdir -p "${BUILD_ROOT}"/var/lib/pacman
    mkdir -p "${BUILD_ROOT}"/var/log
    mkdir -p "${BUILD_ROOT}"/tmp

    mkdir -p "${BUILD_ROOT}"/home

    build_pacman -Syu
    build_pacman --noconfirm -S base
}

function build_pacman {
    pacman --cachedir "/var/cache/pacman/pkg" --root "${BUILD_ROOT}" "$@"
}

function build_pip {
    "${BUILD_ROOT}"/"${MINGW}"/bin/python3.exe -m pip "$@"
}

function build_python {
    "${BUILD_ROOT}"/"${MINGW}"/bin/python3.exe "$@"
}

function build_compileall_pyconly {
    MSYSTEM= build_python -m compileall \
        --invalidation-mode unchecked-hash -b "$@"
}

function build_compileall {
    MSYSTEM= build_python -m compileall \
        --invalidation-mode unchecked-hash "$@"
}

function install_pre_deps {
    pacman -S --needed --noconfirm \
        p7zip \
        git \
        dos2unix \
        mingw-w64-"${ARCH}"-nsis \
        wget \
        mingw-w64-"${ARCH}"-toolchain
}

function install_deps {
    build_pacman --noconfirm -S \
        mingw-w64-"${ARCH}"-gtk3 \
        mingw-w64-"${ARCH}"-python3 \
        mingw-w64-"${ARCH}"-python3-gobject \
        mingw-w64-"${ARCH}"-python3-cairo \
        mingw-w64-"${ARCH}"-python3-pip \
        mingw-w64-"${ARCH}"-python3-numpy \
        mingw-w64-"${ARCH}"-python3-matplotlib \
        mingw-w64-"${ARCH}"-python3-scipy \
        mingw-w64-"${ARCH}"-python3-more-itertools \
        mingw-w64-"${ARCH}"-python3-pbr \
        mingw-w64-"${ARCH}"-python3-pytest

# setuptools: https://github.com/pypa/setuptools/issues/1963
    PIP_REQUIREMENTS="\
setuptools<45.0.0
bidict==0.18.0
lmfit==0.9.12
pbr==5.4.4
asteval==0.9.15
six==1.12.0
uncertainties==3.1.2
pyinstaller==3.6
pywin32-ctypes==0.2.0
pefile==2019.4.18
altgraph==0.17
future==0.18.2
"

    build_pip install --no-deps --no-binary ":all:" --upgrade \
        --force-reinstall $(echo "$PIP_REQUIREMENTS" | tr ["\\n"] [" "])

}

function force_fetch_gxps {
    pushd ".."
    git fetch --all
    git reset --hard origin/master
    popd
}

function install_gxps {
    [ -z "$1" ] && (echo "Missing arg"; exit 1)

    rm -Rf "${REPO_CLONE}"
    git clone "${BASEDIR}"/.. "${REPO_CLONE}"
    pushd "${REPO_CLONE}"

    git checkout "$1" || exit 1

    build_python setup.py install

    local GXPS_PIP_STRING=$(build_pip show "gxps" | grep "Version:")
    # pip seems to crash? Using git method instead
    local GXPS_PIP_STRING=$(build_pip show "gxps" | grep "Version:")
    GXPS_RELEASE=$(echo $GXPS_PIP_STRING | sed -re 's/Version: //g')
    GXPS_VERSION=$(echo $GXPS_RELEASE | sed -re 's/\.[a-z]+.*//g')
    # GXPS_VERSION=$(git describe --abbrev=0 $1)
    # GXPS_RELEASE="${GXPS_VERSION}"
    # if [ "$1" = "master" ]
    # then
    #     local GIT_REV=$(git rev-list --count HEAD)
    #     local GIT_HASH=$(git rev-parse --short HEAD)
    #     GXPS_RELEASE="${GXPS_VERSION}.dev${GIT_REV}-${GIT_HASH}"
    # fi

    popd

    echo "${GXPS_VERSION}" > "${MINGW_ROOT}"/share/gxps/version.txt
    echo "${GXPS_RELEASE}" > "${MINGW_ROOT}"/share/gxps/release.txt
}

function cleanup_before {
    # remove some larger ones
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/512x512"
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/256x256"
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/96x96"
    "${MINGW_ROOT}"/bin/gtk-update-icon-cache-3.0.exe \
        "${MINGW_ROOT}"/share/icons/Adwaita

    # remove some gtk demo icons
    find "${MINGW_ROOT}"/share/icons/hicolor -name "gtk3-*" -exec rm -f {} \;
    "${MINGW_ROOT}"/bin/gtk-update-icon-cache-3.0.exe \
        "${MINGW_ROOT}"/share/icons/hicolor

    # python related, before installing gxps
    rm -Rf "${MINGW_ROOT}"/lib/python3.*/test
    rm -f "${MINGW_ROOT}"/lib/python3.*/lib-dynload/_tkinter*
    rm -Rf "${MINGW_ROOT}"/lib/python3.8/lib2to3/tests
    # cannot remove numpy tests?
#    find "${MINGW_ROOT}"/lib/python3.* -type d -name "test*" \
#        -prune -exec rm -rf {} \;
#    find "${MINGW_ROOT}"/lib/python3.* -type d -name "*_test*" \
#        -prune -exec rm -rf {} \;

    find "${MINGW_ROOT}"/bin -name "*.pyo" -exec rm -f {} \;
    find "${MINGW_ROOT}"/bin -name "*.pyc" -exec rm -f {} \;
}

function move_ico {
    cp gxps.ico "${BUILD_ROOT}"
}

function make_exe {
    [ -z "$1" ] && (echo "Missing arg"; exit 1)

    build_python -m PyInstaller \
        --distpath "${1}" \
        gxps.spec

    mv "${1}"/gxps "${1}"/gxps-win64-"${GXPS_RELEASE}" || true
}

function make_single_exe {
    [ -z "$1" ] && (echo "Missing arg"; exit 1)

    build_python -m PyInstaller \
        --distpath "${1}" \
        --windowed \
        --onefile \
        gxps_onefile.spec

    mv "${1}"/gxps.exe "${1}"/gxps-win64-"${GXPS_RELEASE}".exe || true
}

function make_installer {
    echo "making the installer is not implemented"
}
