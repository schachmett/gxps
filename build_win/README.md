# Building the windows executables

## Setting up MSYS2

* Install MSYS2 from https://msys2.github.io/
* Start the MingGW64 command line and follow the instructions in https://msys2.github.io/:
	- run `pacman -Syu`
	- you may need to restart MSYS2/MinGW64 or even your computer
	- run `pacman -Su` again
	
## Prepare GXPS

* Install git with `pacman -S git`
* Clone this repo with `git clone https://schachmett.com/gxps.git`
* Go to this directory (`cd gxps/build_win`)

If you only want to run GXPS from MSYS2:

* Install the needed dependencies by `./bootstrap.sh`
* Start gxps by `../gxps.py` or `cd .. && ./gxps.py`

If you want to build a windows executable, you don't need `bootstrap.sh`

* Just run `./build.sh`
* Wait
* In the git root directory (`cd ..`), a `dist` folder should appear, containing a `gxps-$version` folder with an `gxps.exe` inside, and a standalone `gxps-$version.exe`
* For now, the standalone `.exe` does not work