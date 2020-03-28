# Building the windows executables

For now, this is only tested on Windows 10. According to the [PyInstaller documentation](https://pyinstaller.readthedocs.io/en/v3.3.1/usage.html#windows), there may be problems with missing `.dll`s on other Windows versions.

## Setting up MSYS2 and preparing GXPS

* Install MSYS2 from https://msys2.github.io/
* Start the MingGW64 command line and follow the instructions in https://msys2.github.io/:
	- run `pacman -Syu`
	- you may need to restart MSYS2/MinGW64 or even your computer
	- run `pacman -Su` again
* Install git with `pacman -S git`
* Clone this repo with `git clone https://schachmett.com/gxps.git`
* Go to this directory (`cd gxps/build_win`)
	
## Running GXPS

If you only want to run GXPS from MSYS2:

* Install the needed dependencies by `./bootstrap.sh`
* Start gxps by `../gxps.py` or `cd .. && ./gxps.py`

## Building GXPS

If you want to build a windows executable, you don't need `bootstrap.sh`.

* Just run `./build.sh`
* Wait
* In the git root directory (`cd ..`), a `dist_win` folder should appear, containing a `gxps-$version` folder with an `gxps.exe` inside, and a standalone `gxps-$version.exe`
* For now, the standalone `.exe` does not work

If you already have the dependencies installed in the `build_win/_build_root/` directory (after running `./build.sh` at least once), you can skip this step and just use `./build.sh rebuild`. This however also forcefully updates the repository from Github, making you lose all local changes to the repo.
You can further customize the build process by commenting out various steps in the `build.sh`.