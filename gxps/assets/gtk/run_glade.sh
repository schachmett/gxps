#!/bin/sh
# Runs the Glade UI designer with gxps catalog from this directory
# Taken from https://github.com/mypaint/mypaint/blob/master/glade/run.sh

dir="$(dirname $0)"
GLADE_CATALOG_SEARCH_PATH="$dir"
echo $GLADE_CATALOG_SEARCH_PATH

if test "x$XDG_DATA_DIRS" = "x"; then
    XDG_DATA_DIRS="/usr/local/share/:/usr/share/"
fi
XDG_DATA_DIRS="${dir}:${XDG_DATA_DIRS}"

export GLADE_CATALOG_SEARCH_PATH
export XDG_DATA_DIRS
exec glade "${dir}/gxps.glade"
