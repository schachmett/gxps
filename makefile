

.PHONY: venv

venv:
	virtualenv venv
	source venv/bin/activate

compile:
	python3 -m compileall -q gxps
	python3 -O -m compileall -q gxps
