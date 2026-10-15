#!/bin/sh
set -eu
cd "$(dirname "$0")"
"$HOME/fad-v001-venv/bin/python" -m build > "$HOME/fad-build.log" 2>&1
python3 -m venv "$HOME/fad-v001-release"
"$HOME/fad-v001-release/bin/pip" install --force-reinstall dist/fad_downloader-0.1.0-py3-none-any.whl > "$HOME/fad-release-install.log" 2>&1
"$HOME/fad-v001-release/bin/fad-downloader" --version
"$HOME/fad-v001-release/bin/fad-downloader" download --demo --workspace "$HOME/fad-v010-release-demo"
"$HOME/fad-v001-release/bin/fad-downloader" verify --workspace "$HOME/fad-v010-release-demo"
"$HOME/fad-v001-release/bin/fad-downloader" catalog --workspace "$HOME/fad-v010-release-demo"
"$HOME/fad-v001-release/bin/pip" freeze --exclude fad-downloader > requirements-linux-tested.txt
"$HOME/fad-v001-venv/bin/pip-audit" -r requirements-linux-tested.txt
