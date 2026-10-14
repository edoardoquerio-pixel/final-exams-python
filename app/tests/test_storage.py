import hashlib
import json
import os

import pytest

from fad_downloader.domain import Account, FadError, ORIGIN
from fad_downloader.storage import SafeRoot, clean_name, components, load_manifest, render_name


@pytest.mark.parametrize(
    "path", ["../escape", "/absolute", "C:/file", "a/../b", "a//b", "a\\b", "a/CON", "a/\x00b"]
)
def test_invalid_relative_paths(path):
    with pytest.raises(FadError):
        components(path)


def test_names_and_templates():
    assert clean_name("CON.txt") == "_CON.txt"
    assert len(clean_name("è" * 200).encode()) <= 160
    assert render_name("{id}_{name}", {"id": 1, "name": "Python"}) == "1_Python"
    for template in ("{name.__class__}", "{name!r}", "{name:10}", "../{name}"):
        with pytest.raises(FadError):
            render_name(template, {"name": "x"})


def test_atomic_failure_preserves_original(tmp_path):
    root = SafeRoot(tmp_path)
    root.write("file.bin", [b"old"])

    def broken():
        yield b"new partial"
        raise OSError("disk full")

    with pytest.raises(OSError):
        root.write("file.bin", broken())
    assert (tmp_path / "file.bin").read_bytes() == b"old"
    assert not list(tmp_path.glob(".part-*"))


def test_change_during_transfer(tmp_path):
    root = SafeRoot(tmp_path)
    root.write("file.bin", [b"old"])
    expected = root.fingerprint("file.bin")

    def modified():
        (tmp_path / "file.bin").write_bytes(b"user edit")
        yield b"server"

    with pytest.raises(FadError, match="cambiato"):
        root.write("file.bin", modified(), expected)
    assert (tmp_path / "file.bin").read_bytes() == b"user edit"


def test_lock_excludes_second_writer(tmp_path):
    root = SafeRoot(tmp_path)
    with root.lock():
        with pytest.raises(FadError, match="utilizzato"):
            with SafeRoot(tmp_path).lock():
                pass
    with root.lock():
        pass


@pytest.mark.skipif(os.name != "posix", reason="Aperture no-follow Linux")
def test_symlink_cannot_escape(tmp_path):
    root = SafeRoot(tmp_path / "work", create=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"safe")
    (root.root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        root.write("link/secret", [b"bad"])
    assert (outside / "secret").read_bytes() == b"safe"
    (root.root / "file").symlink_to(outside / "secret")
    with pytest.raises(FadError):
        root.write("file", [b"bad"])


def test_manifest_account_and_schema(tmp_path):
    root = SafeRoot(tmp_path)
    account = Account(ORIGIN, "1")
    root.write_json(".fad/manifest.json", load_manifest(root, account))
    with pytest.raises(FadError, match="altro account"):
        load_manifest(root, Account(ORIGIN, "2"))
    root.write_json(".fad/manifest.json", {"version": 99, "records": {}})
    with pytest.raises(FadError, match="Schema"):
        load_manifest(root)
    root.write(".fad/manifest.json", [b"{broken"])
    with pytest.raises(FadError, match="corrotto"):
        load_manifest(root)


def test_fingerprint_independent(tmp_path):
    root = SafeRoot(tmp_path)
    size, digest = root.write(".fad/data.json", [json.dumps({"x": 1}).encode()])
    data = (tmp_path / ".fad/data.json").read_bytes()
    assert (size, digest) == (len(data), hashlib.sha256(data).hexdigest())
