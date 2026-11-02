"""Congela le wheel Linux effettivamente provate, con hash per installazione offline."""

from email.parser import Parser
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def main():
    artifacts = Path(__file__).resolve().parent / ".verification-artifacts"
    frozen = artifacts / "production-linux-packages.txt"
    lines = [line for line in frozen.read_text().splitlines() if line and not line.lower().startswith("fad-downloader")]
    expected = {}
    for line in lines:
        name, version = line.split("==")
        expected[normalize(name)] = version
    pinned = artifacts / "production-linux-runtime.txt"
    pinned.write_text("\n".join(lines) + "\n", encoding="utf-8")
    wheelhouse = artifacts / "wheelhouse-linux"
    wheelhouse.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
                    "--only-binary=:all:", "--no-deps", "--dest", str(wheelhouse), "-r", str(pinned)], check=True)
    locked = {}
    for wheel in wheelhouse.glob("*.whl"):
        with zipfile.ZipFile(wheel) as archive:
            metadata = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            package = Parser().parsestr(archive.read(metadata).decode("utf-8"))
        name, version = normalize(package["Name"]), package["Version"]
        if expected.get(name) == version:
            locked[name] = f"{name}=={version} --hash=sha256:{hashlib.sha256(wheel.read_bytes()).hexdigest()}"
    if set(locked) != set(expected):
        raise RuntimeError("Wheel mancanti: lock incompleto")
    (artifacts / "requirements-production-linux.lock").write_text("\n".join(locked[n] for n in sorted(locked)) + "\n", encoding="utf-8")
    checked = [artifacts / name for name in (
        "fad_downloader-0.2.0-py3-none-any.whl", "fad_downloader-0.2.0.tar.gz",
        "requirements-production-linux.lock",
    )]
    (artifacts / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in checked
    ), encoding="utf-8")
    (artifacts / "SHA256.json").write_text(json.dumps({
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in checked
    }, indent=2), encoding="utf-8")
    print(f"Lock Linux creato: {len(locked)} dipendenze con SHA256")


if __name__ == "__main__":
    main()
