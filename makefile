.PHONY: venv clean venv create_venv bump_release dist dist_win build test


venv:
	source venv/bin/activate

create_venv:
	python3 -m venv venv
	source venv/bin/activate

clean:
	rm -Rf build
	rm -Rf dist*
	rm -Rf *.egg-info
	rm -Rf ChangeLog
	rm -Rf AUTHORS
	rm -Rf *.backup
	rm -Rf *~

bump_release:
	@if [ ! -z $(TAG) ] && [ ! -z $(DESCRIPTION) ]; then \
		echo 'git tag -a $(TAG) -m $(DESCRIPTION);' \
		git tag -a $(TAG) -m $(DESCRIPTION); \
		echo 'git push --tags'; \
		git push --tags; \
	else \
		echo "No TAG and/or DESCRIPTION provided."; \
	fi

dist: clean
	python3 setup.py sdist bdist_wheel
	python3 -m twine upload dist/*

dist_win: clean
	rm -Rf build_win/_build_root
	rm -Rf build_win/build
	build_win/build.sh
	
dist_win_re: clean
	build_win/build.sh rebuild
	
build: clean
	python3 setup.py sdist bdist_wheel

test:
	pytest
	

