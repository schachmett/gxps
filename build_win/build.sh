#!/usr/bin/env bash
# This windows building routine was largely adopted from the
# Quod Libet project 
# https://github.com/quodlibet/quodlibet (Copyright 2016 Christoph Reiter)

set -e

BASEDIR="$( cd $( dirname $0 ) && pwd )"
DESTDIR="${BASEDIR}"/_inst
DISTDIR="${BASEDIR}"/gxps_win
source "${BASEDIR}"/_base.sh

function main {
    local GIT_TAG=${1:-"master"}

    [[ -d "${BUILD_ROOT}" ]] && (echo "${BUILD_ROOT} already exists"; exit 1)

    # started from the wrong env -> switch
    if [ $(echo "$MSYSTEM" | tr '[A-Z]' '[a-z]') != "$MINGW" ]; then
        "/${MINGW}.exe" "$0"
        exit $?
    fi

    install_pre_deps
    create_root
    install_deps
#    cleanup_before
    install_gxps "${GIT_TAG}"
    cp gxps.ico "${BUILD_ROOT}"
#    cleanup_after
    make_exe "${DISTDIR}"
#    build_installer
#    build_portable_installer
}

main "$@";
