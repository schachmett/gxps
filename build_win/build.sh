#!/usr/bin/env bash
# This windows building routine was largely adopted from the
# Quod Libet project
# https://github.com/quodlibet/quodlibet (Copyright 2016 Christoph Reiter)

set -e

GXPS_VERSION="0.0.0"
GXPS_VERSION_DESC="UNKOWN"

pushd "$(dirname $0)"
BASEDIR="$(pwd)"
DISTDIR="${BASEDIR}"/../dist_win
source "${BASEDIR}"/_base.sh

function header {
    echo "############################################################"
    echo "      $@"
    echo "############################################################"
}

function main {
    local GIT_TAG=${1:-"master"}
    local REBUILD=""
    if [ "$GIT_TAG" = "rebuild" ]; then
        REBUILD="True"
        GIT_TAG="master"
    fi
    
    if [ ! -z $REBUILD ]; then
        echo "Rebuilding and overwriting local repo from github!"
        read -p "Are you sure to overwrite local repo? [yN]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]
        then
            echo "User aborted"
            exit 1
        else
            echo "Proceeding..."
        fi
    else
        echo "Doing normal build procedure"
    fi

    set_build_root "${BASEDIR}/_build_root"

    if [ -z "${REBUILD}" ]; then
        [[ -d "${BUILD_ROOT}" ]] && (echo "${BUILD_ROOT} already exists"; exit 1)
    fi

    # started from the wrong env -> switch
    if [ $(echo "$MSYSTEM" | tr '[A-Z]' '[a-z]') != "$MINGW" ]; then
        "/${MINGW}.exe" "$0"
        exit $?
    fi

    if [ -z "${REBUILD}" ]; then
        header "Installing tools for building"
        install_pre_deps
        
        header "Creating _build_root directory"
        create_root
        
        header "Installing dependencies"
        install_deps
        
        header "Deleting some annoying files"
        cleanup_before
    else
        header "Skipping _build_root preparation"
        header "Force fetch from git!"
        force_fetch_gxps
    fi
    
    header "Installing GXPS to _build_root"
    install_gxps "${GIT_TAG}"
    move_ico
    
    header "Making Executable in folder"
    make_exe ${DISTDIR}
    
    header "Making one-file Executable not working yet"
#    make_single_exe ${DISTDIR}
    
    header "Making Installer not implemented yet"
#    make_installer
}

main "$@";

popd;
