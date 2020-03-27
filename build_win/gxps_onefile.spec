"""Spec file for PyInstaller."""
# pylint: disable=invalid-name
# pylint: disable=undefined-variable

import os.path
from PyInstaller.utils.hooks import collect_submodules


pathex = os.path.abspath(SPECPATH)
package_dir = "_build_root/mingw64/lib/python3.8/site-packages/gxps/"
datas_dir = "_build_root/mingw64/share/gxps"
icon_path = "gxps.ico"

datas = [(datas_dir, 'data')]
afile = os.path.join(package_dir, "main.py")

block_cipher = None

hiddenimports = collect_submodules("packaging") + \
                collect_submodules("pkg_resources.py2_warn") + \
                collect_submodules("gxps")

a = Analysis(
    [afile],
    pathex=[pathex],
    binaries=None,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="gxps",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    bootloader_ignore_signals=False,
    runtime_tmpdir=None,
    icon=icon_path
)
