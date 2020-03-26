import sys
import os.path
from PyInstaller.utils.hooks import collect_submodules

pathex = "C:/msys64/home/Simon/gxps/build_win/"
package_dir = "_build_root/mingw64/lib/python3.8/site-packages/gxps/"

datas_dir = os.path.join(pathex, "_build_root/mingw64/share/gxps")
package_dir = os.path.join(pathex, package_dir)
afile = os.path.join(package_dir, "main.py")

block_cipher = None

hiddenimports = collect_submodules("packaging") + \
                collect_submodules("pkg_resources.py2_warn") + \
                collect_submodules("gxps")

datas =[
  (datas_dir, 'data')
]


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
    name="gxps-win",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="gxps.ico"
)

