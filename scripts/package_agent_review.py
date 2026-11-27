"""Package committed agent activation inputs for review; never install or activate."""

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED = (
    "LICENSE",
    "apps/api/pyproject.toml", "apps/api/uv.lock", "apps/api/alembic.ini",
    "packages/domain/pyproject.toml", "packages/domain/src/cashlessiq_domain/__init__.py",
    "src/cashlessiq/decision_schema.py", "src/cashlessiq/source_decision.py",
    "src/cashlessiq/source_history.py", "src/cashlessiq/source_recommendation.py",
    "deploy/agent-controller/scope-capture.sql", "deploy/agent-controller/reservation.sql",
    "deploy/agent-controller/receipt-observer.sql",
    "deploy/agent-controller/custody-submission.sql",
    "deploy/agent-controller/custody-publication.sql",
    "deploy/agent-controller/custody-recovery.sql",
    "deploy/agent-controller/single-call.sql",
    "docs/architecture/agent-single-call-custody.md",
    "docs/architecture/agent-single-call-product.md",
    "docs/architecture/agent-single-call-runtime.md",
    "docs/architecture/agent-single-call-supervision.md",
    "docs/architecture/agent-single-call-identity.md",
    *(f"deploy/agent-controller/systemd/ciq-agent-{role}.service.example"
      for role in ("claim", "custody", "receipt")),
    "deploy/agent-controller/README.md",
    "deploy/agent-controller/python-downloads.json",
    "deploy/agent-controller/build-requirements.in",
    "deploy/agent-controller/build-requirements.txt",
)
TREES = {
    "apps/api/src/ciq_api/": (".py", ".json"),
    "apps/api/migrations/": (".py",),
    "src/cashlessiq/rules/": (".py",),
}
MANIFEST = "agent-review.json"
MAX_FILES = 256
MAX_FILE = 2_000_000
MAX_TOTAL = 8_000_000
MAX_TAR = 10_000_000
MAX_COMPRESSED = 4_000_000
ERROR = "Agent review package unconfirmed"


def require(value):
    if not value:
        raise ValueError(ERROR)


def git(*args, input=None):
    # Only read the explicitly chosen checkout, also from root-owned CI fixtures.
    # Replacement refs must not substitute different objects under the pinned SHA.
    result = subprocess.run(["git", "--no-replace-objects", "-c", f"safe.directory={ROOT}", *args],
                            cwd=ROOT, input=input,
                            capture_output=True, timeout=15)
    require(result.returncode == 0)
    return result.stdout


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def committed_files(revision):
    """Read exact allowed blobs from Git, never the operator working tree."""
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision))
    require(git("rev-parse", "--verify", revision + "^{commit}").decode().strip() == revision)
    inventory = git("ls-tree", "-rlz", "--full-tree", revision, "--", *FIXED, *TREES)
    entries = {}
    for record in inventory.split(b"\0"):
        if not record:
            continue
        header, raw_name = record.split(b"\t", 1)
        mode, kind, oid, size = header.split()
        name = raw_name.decode("utf-8")
        allowed = name in FIXED or any(
            name.startswith(prefix) and name.endswith(suffixes)
            for prefix, suffixes in TREES.items()
        )
        if not allowed:
            continue
        require(mode == b"100644" and kind == b"blob" and name not in entries
                and size.isdigit() and int(size) <= MAX_FILE)
        entries[name] = (oid, int(size))
    require(set(FIXED) <= entries.keys() and len(entries) <= MAX_FILES)
    require(all(any(name.startswith(prefix) for name in entries) for prefix in TREES))
    require(sum(size for _, size in entries.values()) <= MAX_TOTAL)
    raw = git("cat-file", "--batch", input=b"".join(
        oid + b"\n" for oid, _ in entries.values()))
    stream = io.BytesIO(raw)
    files = {}
    for name, (oid, size) in entries.items():
        require(stream.readline() == oid + b" blob " + str(size).encode() + b"\n")
        files[name] = stream.read(size)
        require(len(files[name]) == size and stream.read(1) == b"\n")
    require(stream.read() == b"")
    return files


def manifest(revision, files):
    return json.dumps({
        "schema": "agent-activation-review-v1", "revision": revision,
        "activation": "disabled", "files": {name: sha256(data) for name, data in files.items()},
    }, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def archive_bytes(revision, files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted({**files, MANIFEST: manifest(revision, files)}.items()):
            item = tarfile.TarInfo(name)
            item.mode, item.size, item.mtime = 0o644, len(data), 0
            archive.addfile(item, io.BytesIO(data))
    return stream.getvalue()


def encode(revision, files):
    return gzip.compress(archive_bytes(revision, files), mtime=0)


def verify_data(data, revision, files):
    """Compare with independently pinned Git blobs, not self-reported hashes."""
    require(len(data) <= MAX_COMPRESSED)
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
        raw = compressed.read(MAX_TAR + 1)
    # Compare the entire canonical tar, including headers, padding and end markers.
    # Never parse/extract an incoming tar or accept hidden trailing/concatenated entries.
    require(len(raw) <= MAX_TAR and raw == archive_bytes(revision, files))


def create(revision):
    files = committed_files(revision)
    data = encode(revision, files)
    verify_data(data, revision, files)
    output = ROOT / "output/agent-review"
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"cashlessiq-agent-review-{revision}.tar.gz"
    with path.open("xb") as stream:  # Includes dangling symlinks; never replace an existing entry.
        stream.write(data)
    return path, sha256(data), len(files)


def stage(revision, destination):
    """Materialize only pinned public blobs in a fresh caller-owned build tree.

    Read all Git inputs before creating output. This does not extract an incoming
    archive, execute a build, or install anything. The parent must already exist
    and remain controlled by the caller; concurrent hostile writers are outside
    this preparation helper's boundary. Preserve partial output on failure.
    """
    files = committed_files(revision)
    destination.mkdir(mode=0o755)  # Refuse existing trees and dangling symlinks.
    for name, data in sorted(files.items()):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    # Completion metadata is written last, never used as its own trust anchor.
    with (destination / MANIFEST).open("xb") as stream:
        stream.write(manifest(revision, files))
    return len(files)


def verify(path, revision):
    files = committed_files(revision)
    with path.open("rb") as stream:
        data = stream.read(MAX_COMPRESSED + 1)
    verify_data(data, revision, files)
    return sha256(data), len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify", "stage"))
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--revision", required=True, help="independently selected full commit SHA")
    args = parser.parse_args()
    if (args.action in ("verify", "stage")) != (args.path is not None):
        parser.error("verify and stage require a path; create does not")
    try:
        if args.action == "stage":
            count = stage(args.revision, args.path)
            print(f"Staged {count} committed files; activation disabled.")
            return
        if args.action == "create":
            path, digest, count = create(args.revision)
            print(f"Created review package: {path}")
        else:
            digest, count = verify(args.path, args.revision)
        print(f"Verified {count} committed files; SHA-256 {digest}; activation disabled.")
    except Exception:
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
