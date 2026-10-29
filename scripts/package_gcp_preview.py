"""Create and verify a minimal, credential-free GCP preview runtime bundle."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/gcp-preview"
FILES = (
    "compose.owner-preview.yml",
    "compose.preview-small.yml",
    "compose.mvp.yml",
    "compose.gcp-preview.yml",
    "deploy/owner-preview/Caddyfile",
    "deploy/gcp-preview/plan.json",
    "scripts/owner_preview.py",
    "scripts/check_gcp_preview_plan.py",
    "scripts/gcp_preview_runtime.py",
)
MANIFEST = "manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def committed_revision() -> str:
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *FILES],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *FILES], cwd=ROOT, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def add_bytes(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    entry = tarfile.TarInfo(name)
    entry.size = len(data)
    entry.mode = 0o644
    entry.mtime = 0
    archive.addfile(entry, io.BytesIO(data))


def create() -> Path:
    revision = committed_revision()
    files = {name: (ROOT / name).read_bytes() for name in FILES}
    manifest = {
        "revision": revision,
        "project_id": "cashlessiq-dev-rush",
        "files": {name: sha256(data) for name, data in files.items()},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / f"cashlessiq-gcp-preview-{revision[:12]}.tar.gz"
    if destination.exists():
        raise ValueError("Bundle already exists; refusing to replace it")
    with tarfile.open(destination, "x:gz") as archive:
        for name, data in files.items():
            add_bytes(archive, name, data)
        add_bytes(archive, MANIFEST, json.dumps(manifest, sort_keys=True).encode() + b"\n")
    verify(destination)
    digest = sha256(destination.read_bytes())
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n"
    )
    print(f"Created minimal runtime bundle: {destination}")
    print(f"SHA-256: {digest}")
    print("No credentials, application source, owner video or cloud resource included.")
    return destination


def verify(path: Path) -> dict[str, object]:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)) or set(names) != {*FILES, MANIFEST}:
            raise ValueError("Bundle contains unexpected or duplicate entries")
        if any(not member.isfile() for member in members):
            raise ValueError("Bundle must contain regular files only")
        contents = {member.name: archive.extractfile(member).read() for member in members}
    manifest = json.loads(contents.pop(MANIFEST))
    if manifest["project_id"] != "cashlessiq-dev-rush":
        raise ValueError("Bundle targets the wrong GCP project")
    actual = {name: sha256(data) for name, data in contents.items()}
    if manifest["files"] != actual:
        raise ValueError("Bundle file digest mismatch")
    print(f"Verified minimal runtime bundle at revision {manifest['revision'][:12]}.")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "create":
        if args.path:
            parser.error("create does not accept a path")
        create()
    else:
        if not args.path:
            parser.error("verify requires a bundle path")
        verify(args.path)


if __name__ == "__main__":
    main()
