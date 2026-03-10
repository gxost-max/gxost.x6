PY=python

help:
	@echo "Targets: run, install-win, install-nix, publish"

run:
	$(PY) gxost.x6.py

install-win:
	powershell -ExecutionPolicy Bypass -File .\install.ps1

install-nix:
	bash ./install.sh

publish:
	powershell -ExecutionPolicy Bypass -File .\publish.ps1 -User YOUR_USER -Repo gxost.x6
