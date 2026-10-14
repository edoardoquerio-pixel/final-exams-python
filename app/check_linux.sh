#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m venv "$HOME/fad-v001-venv"
"$HOME/fad-v001-venv/bin/pip" install -e '.[dev]' > "$HOME/fad-install.log" 2>&1
xvfb-run -a "$HOME/fad-v001-venv/bin/python" -m pytest -q
