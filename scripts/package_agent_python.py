"""Prepare/verify a pinned public interpreter archive; never extract or execute it."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

from scripts import package_agent_release as release

KEY = "cpython-3.11.15-linux-x86_64-gnu"
PIN = "deploy/agent-controller/python-downloads.json"
METADATA = "python-downloads.json"
MANIFEST = "agent-python.json"
MAX_ARCHIVE = 64_000_000
ERROR = "Agent interpreter bundle unconfirmed"


def require(value):
    if not value:
        raise ValueError(ERROR)


def expected(revision):
    raw = release.review.committed_files(revision)[PIN]
    metadata = json.loads(raw)
    require(set(metadata) == {KEY})
    pin = metadata[KEY]
    url = urlsplit(pin["url"])
    require(url.scheme == "https" and url.netloc == "github.com"
            and url.path.startswith("/astral-sh/python-build-standalone/releases/download/")
            and not url.query and not url.fragment
            and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]))
    name = unquote(url.path.rsplit("/", 1)[1])
    require(re.fullmatch(r"[A-Za-z0-9_.+-]+\.tar\.gz", name))
    return name, pin, raw


def manifest(revision, name, data):
    return release.canonical({
        "schema": "agent-python-v1", "revision": revision,
        "target": release.dependencies.TARGET, "activation": "disabled",
        "archive": {"name": name, "size": len(data),
                    "sha256": release.review.sha256(data)},
    })


def verify(directory, revision):
    name, pin, raw = expected(revision)
    release.inventory(directory, {name, METADATA, MANIFEST})
    data = release.dependencies.read_regular(directory / name, MAX_ARCHIVE)
    require(data and release.review.sha256(data) == pin["sha256"])
    require(release.dependencies.read_regular(directory / METADATA, len(raw)) == raw)
    receipt = manifest(revision, name, data)
    require(release.dependencies.read_regular(directory / MANIFEST, len(receipt)) == receipt)
    return directory / name


def create(directory, revision):
    name, pin, raw = expected(revision)
    directory.mkdir()  # Refuse existing directories and links before any download.
    # GitHub redirects to its public release asset host. The committed SHA256 is
    # the authority for these inert bytes, not a redirect or incoming manifest.
    with urlopen(pin["url"], timeout=30) as response:
        require(urlsplit(response.geturl()).scheme == "https")
        data = response.read(MAX_ARCHIVE + 1)
    require(0 < len(data) <= MAX_ARCHIVE and release.review.sha256(data) == pin["sha256"])
    for filename, value in ((name, data), (METADATA, raw),
                            (MANIFEST, manifest(revision, name, data))):
        with (directory / filename).open("xb") as stream:
            stream.write(value)
    return verify(directory, revision)


def local_metadata(directory, revision, destination):
    """Write invocation-local uv metadata only after offline archive verification.

    The caller owns the parent and excludes concurrent writers. This does not
    install uv, extract the archive, or claim the destination host is safe.
    """
    archive = verify(directory, revision)
    _, pin, _ = expected(revision)
    data = release.canonical({KEY: {**pin, "url": archive.resolve(strict=True).as_uri()}})
    with destination.open("xb") as stream:
        stream.write(data)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    try:
        (create if args.action == "create" else verify)(args.directory, args.revision)
        print("Verified pinned interpreter archive; activation disabled.")
    except Exception:
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
