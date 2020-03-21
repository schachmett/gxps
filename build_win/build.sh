#!/usr/bin/env bash
# This windows building routine was largely adopted from the
# Quod Libet project 
# https://github.com/quodlibet/quodlibet (Copyright 2016 Christoph Reiter)

DIR="$( cd $( dirname $0 ) && pwd )"
source "$DIR"/_base.sh

function main {
    local GIT_TAG=${1:-"master"}

    [[ -d "${BUILD_ROOT}" ]] && (echo "${BUILD_ROOT} already exists"; exit 1)

    # started from the wrong env -> switch
    if [ $(echo "$MSYSTEM" | tr '[A-Z]' '[a-z]') != "$MINGW" ]; then
        "/${MINGW}.exe" "$0"
        exit $?
    fi

    install_pre_deps
#    create_root
#    install_deps
#    cleanup_before
#    install_quodlibet "$GIT_TAG"
#    cleanup_after
#    build_installer
#    build_portable_installer
}

main "$@";
