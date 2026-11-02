#!/bin/bash
# Test sintetici: mount temporaneo POSIX sotto il progetto; nessun accesso FAD.
set -euo pipefail
cd "$(dirname "$0")"
project_app=$PWD
if [[ ${1:-} == --worker ]]; then
    work=$2
    # xvfb-run/xauth require a temporary path without spaces on this installation.
    export PYTHONDONTWRITEBYTECODE=1 TMPDIR="$(basename "$work")" PIP_CACHE_DIR="$work/pip-cache"
    export XDG_CONFIG_HOME="$work/config" XDG_DATA_HOME="$work/data" XDG_STATE_HOME="$work/state"
    test_python="$HOME/fad-v001-venv/bin/python"
    "$test_python" -B --version
    xvfb-run -a "$test_python" -B -c 'import tkinter as tk; root=tk.Tk(); root.destroy(); print("GUI preflight OK")'
    xvfb-run -a "$test_python" -B -m pytest -q -rs -p no:cacheprovider "--basetemp=$work/tests" tests
    python3 -m venv "$work/release"
    release_python="$work/release/bin/python"
    if [[ -f .verification-artifacts/requirements-production-linux.lock ]]; then
        "$release_python" -m pip install --no-index --require-hashes --find-links .verification-artifacts/wheelhouse-linux -r .verification-artifacts/requirements-production-linux.lock
        "$release_python" -m pip install --no-index --no-deps "$work/fad_downloader-0.2.0-py3-none-any.whl"
    else
        "$release_python" -m pip install --disable-pip-version-check "$work/fad_downloader-0.2.0-py3-none-any.whl"
    fi
    "$release_python" -B -m pip check
    "$work/release/bin/fad-downloader" --version
    "$release_python" -B smoke_release.py
    "$release_python" -m pip freeze > .verification-artifacts/production-linux-packages.txt
    "$release_python" -m pip install --disable-pip-version-check pytest pypdf
    "$release_python" -B -c 'import fad_downloader; from pathlib import Path; import sys; assert Path(fad_downloader.__file__).is_relative_to(Path(sys.prefix)); print("Installed wheel import OK")'
    xvfb-run -a "$release_python" -B -m pytest -q -rs -p no:cacheprovider "--basetemp=$work/release-tests" tests
    xvfb-run -a "$release_python" -B stress_acceptance.py "$work/stress"
    if [[ ${3:-} == --compat ]]; then
        "$release_python" -m pip install --disable-pip-version-check uv
        export UV_PYTHON_INSTALL_DIR="$work/pythons" UV_PYTHON_BIN_DIR="$work/python-bin" UV_CACHE_DIR="$work/uv-cache"
        uv="$work/release/bin/uv"
        "$uv" python install --help > "$work/uv-python-help.txt"
        grep -q -- '--install-dir' "$work/uv-python-help.txt"
        "$uv" python install --install-dir "$work/pythons" 3.10 3.12
        for python_version in 3.10 3.12; do
            "$uv" venv --python "$python_version" --seed "$work/python-$python_version"
            compatibility_python="$work/python-$python_version/bin/python"
            "$compatibility_python" -m pip install --disable-pip-version-check "$work/fad_downloader-0.2.0-py3-none-any.whl" pytest pypdf
            "$compatibility_python" -B --version
            "$compatibility_python" -m pip check
            xvfb-run -a "$compatibility_python" -B -m pytest -q -rs -p no:cacheprovider "--basetemp=$work/tests-$python_version" tests
            "$compatibility_python" -m pip freeze > ".verification-artifacts/production-python-$python_version-packages.txt"
        done
    fi
    exit
fi
if [[ $EUID != 0 || ${1:-} != --mount || -z ${2:-} ]]; then
    echo "Uso: come root, bash check_production_linux.sh --mount UTENTE_LINUX" >&2
    exit 2
fi
test_user=$2
getent passwd "$test_user" >/dev/null
mount_dir=$(mktemp -d "$project_app/.verification-posix-XXXXXX")
test ! -L "$mount_dir"
mount -t tmpfs -o size=1536m,mode=1777 tmpfs "$mount_dir"
trap 'umount "$mount_dir"' EXIT
cp .verification-artifacts/fad_downloader-0.2.0-py3-none-any.whl "$mount_dir/"
chmod 644 "$mount_dir/fad_downloader-0.2.0-py3-none-any.whl"
runuser -u "$test_user" -- bash "$project_app/check_production_linux.sh" --worker "$mount_dir" "${3:-}"
