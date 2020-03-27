#!/usr/bin/env bash
# Runs the Glade UI designer with gxps catalog from this directory
# Modified from https://github.com/mypaint/mypaint/blob/master/glade/run.sh

GLADEPATH="$(dirname $0)"/data/ui
GLADE_CATALOG_SEARCH_PATH="${GLADEPATH}"

MODE=${1:-"glade"}
if [ "${MODE}" = "gedit" ]; then
    gedit "${GLADEPATH}"/gxps.glade &
elif [ "${MODE}" = "catalog" ]; then
    gedit "${GLADEPATH}"/gxps_catalog.xml &
else
    if [ -z "${XDG_DATA_DIRS}" ]; then
        XDG_DATA_DIRS="/usr/local/share/:/usr/share/"
    fi
    XDG_DATA_DIRS="${GLADEPATH}:${XDG_DATA_DIRS}"

    export GLADE_CATALOG_SEARCH_PATH
    export XDG_DATA_DIRS

    glade "${GLADEPATH}"/gxps.glade &> /dev/null &
fi
