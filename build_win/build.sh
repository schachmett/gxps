#!/usr/bin/env bash
# This windows building routine was largely adopted from the
# Quod Libet project
# https://github.com/quodlibet/quodlibet (Copyright 2016 Christoph Reiter)

set -e

GXPS_VERSION="0.0.0"
GXPS_VERSION_DESC="UNKOWN"

BASEDIR="$(dirname $0)"
cd "${BASEDIR}"
DISTDIR="${BASEDIR}"/../dist_win
source "${BASEDIR}"/_base.sh

function main {
    local GIT_TAG=${1:-"master"}

    set_build_root "${BASEDIR}/_build_root"

    [[ -d "${BUILD_ROOT}" ]] && (echo "${BUILD_ROOT} already exists"; exit 1)

    # started from the wrong env -> switch
    if [ $(echo "$MSYSTEM" | tr '[A-Z]' '[a-z]') != "$MINGW" ]; then
        "/${MINGW}.exe" "$0"
        exit $?
    fi

    echo "###########################################"
    echo "Installing tools for building"
    install_pre_deps
    echo "###########################################"
    echo "Creating _build_root directory"
    create_root
    echo "###########################################"
    echo "Installing dependencies"
    install_deps
    echo "###########################################"
    echo "Deleting some annoying files"
    cleanup_before
    echo "###########################################"
    echo "Installing GXPS to _build_root"
    install_gxps "${GIT_TAG}"
    move_ico
    echo "###########################################"
    echo "Making Executable in folder"
    make_exe ${DISTDIR}
    echo "###########################################"
    echo "Making one-file Executable"
    make_single_exe ${DISTDIR}
    echo "###########################################"
    echo "Making Installer"
    make_installer
}

main "$@";
