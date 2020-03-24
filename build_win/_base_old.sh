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
GXPS_VERSION="0.8.1"
GXPS_VERSION_DESC="win-0.8.1"

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

set_build_root "${BASEDIR}/_build_root"

function build_pacman {
    pacman --cachedir "/var/cache/pacman/pkg" --root "${BUILD_ROOT}" "$@"
}

function build_pip {
    "${BUILD_ROOT}"/"${MINGW}"/bin/python3.exe -m pip "$@"
}

function build_python {
    "${BUILD_ROOT}"/"${MINGW}"/bin/python3.exe "$@"
}

#function build_compileall_pyconly {
#    MSYSTEM= build_python -m compileall --invalidation-mode unchecked-hash -b "$@"
#}

#function build_compileall {
#    MSYSTEM= build_python -m compileall --invalidation-mode unchecked-hash "$@"
#}

function install_pre_deps {
    pacman -S --needed --noconfirm \
        p7zip \
        git \
        dos2unix \
        mingw-w64-"${ARCH}"-nsis \
        wget \
        mingw-w64-"${ARCH}"-toolchain
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

#function extract_installer {
#    [ -z "$1" ] && (echo "Missing arg"; exit 1)

#    mkdir -p "$BUILD_ROOT"
#    7z x -o"$BUILD_ROOT"/"$MINGW" "$1"
#    rm -rf "$MINGW_ROOT"/'$PLUGINSDIR' "$MINGW_ROOT"/*.txt "$MINGW_ROOT"/*.nsi
#}

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

    PIP_REQUIREMENTS="\
setuptools<45.0.0
bidict==0.18.0
lmfit==0.9.12
pbr==5.4.4
asteval==0.9.15
six==1.12.0
uncertainties==3.1.2
"

    build_pip install --no-deps --no-binary ":all:" --upgrade \
        --force-reinstall $(echo "$PIP_REQUIREMENTS" | tr ["\\n"] [" "])

    #TODO add more?
    build_pacman --noconfirm -Rdds \
        mingw-w64-"${ARCH}"-shared-mime-info \
        mingw-w64-"${ARCH}"-python-pip 

    build_pacman --noconfirm -Rdds mingw-w64-"${ARCH}"-python2 || true

    build_pacman -S --noconfirm mingw-w64-"${ARCH}"-python3-setuptools
}

function install_gxps {
    [ -z "$1" ] && (echo "Missing arg"; exit 1)

    rm -Rf "${REPO_CLONE}"
    git clone "${BASEDIR}"/.. "${REPO_CLONE}"

    (cd "${REPO_CLONE}" && git checkout "$1") || exit 1

    build_python "${REPO_CLONE}"/setup.py install

#    # Create launchers
#    python3 "${MISC}"/create-launcher.py \
#        "${GXPS_VERSION}" "${MINGW_ROOT}"/bin

#    GXPS_VERSION=$(MSYSTEM= build_python -c \
#        "import gxps; import sys; sys.stdout.write(gxps.__version__)")
    GXPS_VERSION=$(git describe --abbrev=0 $1)
    GXPS_VERSION_DESC="$GXPS_VERSION"
    if [ "$1" = "master" ]
    then
        local GIT_REV=$(git rev-list --count HEAD)
        local GIT_HASH=$(git rev-parse --short HEAD)
        GXPS_VERSION_DESC="$GXPS_VERSION-rev$GIT_REV-$GIT_HASH"
    fi

#    build_compileall -d "" -f -q "$(cygpath -w "${MINGW_ROOT}")"
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
    find "${MINGW_ROOT}"/lib/python3.* -type d -name "test*" \
        -prune -exec rm -rf {} \;
    find "${MINGW_ROOT}"/lib/python3.* -type d -name "*_test*" \
        -prune -exec rm -rf {} \;

    find "${MINGW_ROOT}"/bin -name "*.pyo" -exec rm -f {} \;
    find "${MINGW_ROOT}"/bin -name "*.pyc" -exec rm -f {} \;

    build_compileall_pyconly -d "" -f -q "$(cygpath -w "${MINGW_ROOT}")"
    find "${MINGW_ROOT}" -name "*.py" -exec rm -f {} \;
    find "${MINGW_ROOT}" -type d -name "__pycache__" -prune -exec rm -rf {} \;
}

function cleanup_after {
    # delete translations we don't support
    for d in "${MINGW_ROOT}"/share/locale/*/LC_MESSAGES; do
        if [ ! -f "${d}"/gxps.mo ]; then
            rm -Rf "${d}"
        fi
    done

    find "${MINGW_ROOT}" -regextype "posix-extended" -name "*.exe" -a ! \
        -iregex ".*/(gxps-)[^/]*\\.exe" \
        -exec rm -f {} \;

    rm -Rf "${MINGW_ROOT}"/libexec
    rm -Rf "${MINGW_ROOT}"/share/gtk-doc
    rm -Rf "${MINGW_ROOT}"/include
    rm -Rf "${MINGW_ROOT}"/var
    rm -Rf "${MINGW_ROOT}"/etc/config.site
    rm -Rf "${MINGW_ROOT}"/etc/pki
    rm -Rf "${MINGW_ROOT}"/etc/pkcs11
    rm -Rf "${MINGW_ROOT}"/etc/gtk-3.0/im-multipress.conf
    rm -Rf "${MINGW_ROOT}"/share/zsh
    rm -Rf "${MINGW_ROOT}"/share/pixmaps
    rm -Rf "${MINGW_ROOT}"/share/gnome-shell
    rm -Rf "${MINGW_ROOT}"/share/dbus-1
    rm -Rf "${MINGW_ROOT}"/share/gir-1.0
    rm -Rf "${MINGW_ROOT}"/share/doc
    rm -Rf "${MINGW_ROOT}"/share/man
    rm -Rf "${MINGW_ROOT}"/share/info
    rm -Rf "${MINGW_ROOT}"/share/mime
    rm -Rf "${MINGW_ROOT}"/share/gettext
    rm -Rf "${MINGW_ROOT}"/share/libtool
    rm -Rf "${MINGW_ROOT}"/share/licenses
    rm -Rf "${MINGW_ROOT}"/share/appdata
    rm -Rf "${MINGW_ROOT}"/share/aclocal
    rm -Rf "${MINGW_ROOT}"/share/ffmpeg
    rm -Rf "${MINGW_ROOT}"/share/vala
    rm -Rf "${MINGW_ROOT}"/share/readline
    rm -Rf "${MINGW_ROOT}"/share/xml
    rm -Rf "${MINGW_ROOT}"/share/bash-completion
    rm -Rf "${MINGW_ROOT}"/share/common-lisp
    rm -Rf "${MINGW_ROOT}"/share/emacs
    rm -Rf "${MINGW_ROOT}"/share/gdb
    rm -Rf "${MINGW_ROOT}"/share/libcaca
    rm -Rf "${MINGW_ROOT}"/share/gettext
    rm -Rf "${MINGW_ROOT}"/share/gst-plugins-base
    rm -Rf "${MINGW_ROOT}"/share/gst-plugins-bad
    rm -Rf "${MINGW_ROOT}"/share/libgpg-error
    rm -Rf "${MINGW_ROOT}"/share/p11-kit
    rm -Rf "${MINGW_ROOT}"/share/pki
    rm -Rf "${MINGW_ROOT}"/share/thumbnailers
    rm -Rf "${MINGW_ROOT}"/share/gtk-3.0
    rm -Rf "${MINGW_ROOT}"/share/nghttp2
    rm -Rf "${MINGW_ROOT}"/share/themes
    rm -Rf "${MINGW_ROOT}"/share/fontconfig
    rm -Rf "${MINGW_ROOT}"/share/gettext-*
    rm -Rf "${MINGW_ROOT}"/share/gstreamer-1.0
    rm -Rf "${MINGW_ROOT}"/share/installed-tests
    rm -Rf "${MINGW_ROOT}"/share/fonts
    rm -Rf "${MINGW_ROOT}"/share/vulcan
    rm -Rf "${MINGW_ROOT}"/share/iso-codes
    rm -Rf "${MINGW_ROOT}"/share/openal
    rm -Rf "${MINGW_ROOT}"/share/GConf
    rm -Rf "${MINGW_ROOT}"/share/metainfo

    find "${MINGW_ROOT}"/share/glib-2.0 -type f ! \
        -name "*.compiled" -exec rm -f {} \;

    rm -Rf "${MINGW_ROOT}"/lib/cmake
    rm -Rf "${MINGW_ROOT}"/lib/gettext
    rm -Rf "${MINGW_ROOT}"/lib/gtk-3.0
    rm -Rf "${MINGW_ROOT}"/lib/mpg123
    rm -Rf "${MINGW_ROOT}"/lib/p11-kit
    rm -Rf "${MINGW_ROOT}"/lib/pkcs11
    rm -Rf "${MINGW_ROOT}"/lib/ruby
    rm -Rf "${MINGW_ROOT}"/lib/engines

    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstvpx.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstdaala.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstdvdread.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstopenal.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstopenexr.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstopenh264.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstresindvd.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstassrender.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstx265.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstwebp.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstopengl.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstmxf.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstfaac.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstschro.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstrtmp.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstzbar.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstfdkaac.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstaom.dll

    rm -f "${MINGW_ROOT}"/bin/libharfbuzz-icu-0.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstcacasink.dll
    rm -f "${MINGW_ROOT}"/bin/libgstopencv-1.0-0.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstopencv.dll
    rm -Rf "${MINGW_ROOT}"/lib/python2.*

    find "${MINGW_ROOT}" -name "*.a" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.whl" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.h" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.la" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.sh" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.jar" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.def" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.cmd" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.cmake" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.pc" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.desktop" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.manifest" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.pyo" -exec rm -f {} \;

    find "${MINGW_ROOT}"/bin -name "*-config" -exec rm -f {} \;
    find "${MINGW_ROOT}"/bin -name "easy_install*" -exec rm -f {} \;
    find "${MINGW_ROOT}" -regex ".*/bin/[^.]+" -exec rm -f {} \;
    find "${MINGW_ROOT}" -regex ".*/bin/[^.]+\\.[0-9]+" -exec rm -f {} \;

    find "${MINGW_ROOT}" -name "gtk30-properties.mo" -exec rm -rf {} \;
    find "${MINGW_ROOT}" -name "gettext-tools.mo" -exec rm -rf {} \;
    find "${MINGW_ROOT}" -name "libexif-12.mo" -exec rm -rf {} \;
    find "${MINGW_ROOT}" -name "xz.mo" -exec rm -rf {} \;
    find "${MINGW_ROOT}" -name "libgpg-error.mo" -exec rm -rf {} \;

    find "${MINGW_ROOT}" -name "old_root.pem" -exec rm -rf {} \;
    find "${MINGW_ROOT}" -name "weak.pem" -exec rm -rf {} \;

    find "${MINGW_ROOT}"/bin -name "*.pyo" -exec rm -f {} \;
    find "${MINGW_ROOT}"/bin -name "*.pyc" -exec rm -f {} \;

    build_python "${MISC}/depcheck.py" --delete

    find "${MINGW_ROOT}" -type d -empty -delete
}

function build_exe {
    build_python -m PyInstaller --clean \
        --distpath ${1} \
        --workpath _build \
        --paths _inst/usr/lib/gxps \    #TODO DESTDIR
        gxps.spec
}

function do_make {
    make install PREFIX=/usr DESTDIR="${1}"
}


#function build_installer {
#    BUILDPY=$(echo "${MINGW_ROOT}"/lib/python3.*/site-packages/gxps)/build.py
#    cp "${REPO_CLONE}"/build_win/build.py "$BUILDPY"
#    echo 'BUILD_TYPE = u"windows"' >> "$BUILDPY"
#    echo "BUILD_VERSION = $BUILD_VERSION" >> "$BUILDPY"
#    (cd "$REPO_CLONE" && echo "BUILD_INFO = u\"$(git rev-parse --short HEAD)\"" >> "$BUILDPY")
#    build_compileall -d "" -q -f "$BUILDPY"

#    cp "${MISC}"/gxps.ico "${BUILD_ROOT}"
#    (cd "${MINGW_ROOT}" && makensis -NOCD -DVERSION="$GXPS_VERSION_DESC" "${MISC}"/win_installer.nsi)

#    mv "${MINGW_ROOT}/gxps-LATEST.exe" "$DIR/gxps-$GXPS_VERSION_DESC-installer.exe"
#}

#function build_portable_installer {
#    BUILDPY=$(echo "${MINGW_ROOT}"/lib/python3.*/site-packages/gxps)/build.py
#    cp "${REPO_CLONE}"/build_win/build.py "$BUILDPY"
#    echo 'BUILD_TYPE = u"windows-portable"' >> "$BUILDPY"
#    echo "BUILD_VERSION = $BUILD_VERSION" >> "$BUILDPY"
#    (cd "$REPO_CLONE" && echo "BUILD_INFO = u\"$(git rev-parse --short HEAD)\"" >> "$BUILDPY")
#    build_compileall -d "" -q -f "$BUILDPY"

#    local PORTABLE="$DIR/gxps-$GXPS_VERSION_DESC-portable"

#    rm -rf "$PORTABLE"
#    mkdir "$PORTABLE"
#    #TODO
##    cp "$MISC"/gxps.lnk "$PORTABLE"
#    cp "$MISC"/README-PORTABLE.txt "$PORTABLE"/README.txt
#    unix2dos "$PORTABLE"/README.txt
#    mkdir "$PORTABLE"/config
#    cp -RT "${MINGW_ROOT}" "$PORTABLE"/data

#    rm -Rf 7zout 7z1604.exe
#    7z a payload.7z "$PORTABLE"
#    wget -P "$DIR" -c http://www.7-zip.org/a/7z1604.exe
#    7z x -o7zout 7z1604.exe
#    cat 7zout/7z.sfx payload.7z > "$PORTABLE".exe
#    rm -Rf 7zout 7z1604.exe payload.7z "$PORTABLE"
}
