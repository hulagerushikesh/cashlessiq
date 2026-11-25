"""Fetch/verify locked CPython 3.11 Linux x86-64 wheels; never install or activate."""

import argparse
import json
import os
import re
import stat
import tomllib
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from scripts import package_agent_review as review

TARGET = "cpython-311-manylinux_2_36-x86_64"
MAX_WHEEL = 32_000_000
MAX_TOTAL = 96_000_000
ERROR = "Agent dependency bundle unconfirmed"
# Deliberately closed to the markers present in the reviewed runtime graph.
# New lock markers require review rather than evaluation as Python or guessing.
MARKERS = {
    None: True,
    "platform_python_implementation != 'PyPy'": True,
    "implementation_name != 'PyPy'": True,
    "implementation_name != 'pypy'": True,
    "sys_platform == 'win32'": False,
}


def require(value):
    if not value:
        raise ValueError(ERROR)


def compatible(filename):
    """Narrow target tags: CPython 3.11, glibc <= 2.36, x86-64; no musl/macOS."""
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", filename):
        return False
    parts = filename[:-4].split("-")
    if len(parts) not in (5, 6):
        return False
    python, abi, platforms = parts[-3:]
    pure = abi == "none" and bool(set(python.split(".")) & {"py3", "py311", "cp311"})
    native = python == "cp311" and abi == "cp311"
    stable = bool(re.fullmatch(r"cp3(?:[2-9]|10|11)", python)) and abi == "abi3"
    if not (pure or native or stable):
        return False
    allowed = {f"manylinux_2_{minor}_x86_64" for minor in range(5, 37)}
    allowed |= {"manylinux1_x86_64", "manylinux2010_x86_64", "manylinux2014_x86_64"}
    return any(tag in allowed or (tag == "any" and pure) for tag in platforms.split("."))


def selected_wheels(lock):
    packages = {item["name"]: item for item in lock["package"]}
    require(len(packages) == len(lock["package"]) and lock["requires-python"] == "==3.11.*")
    require(packages["cashlessiq-api"]["source"] == {"editable": "."}
            and packages["cashlessiq-domain"]["source"] == {"directory": "../../packages/domain"})
    visited = set()

    def visit(name, extra=""):
        if (name, extra) in visited:
            return
        require(len(visited) < 128)
        visited.add((name, extra))
        package = packages[name]
        dependencies = (package.get("dependencies", []) if not extra
                        else package["optional-dependencies"][extra])
        for dependency in dependencies:
            require(set(dependency) <= {"name", "marker", "extra"})
            marker = dependency.get("marker")
            require(marker in MARKERS)
            if MARKERS[marker]:
                visit(dependency["name"])
                for selected_extra in dependency.get("extra", []):
                    visit(dependency["name"], selected_extra)

    visit("cashlessiq-api")
    selected = {}
    for name in sorted({name for name, _ in visited} - {"cashlessiq-api", "cashlessiq-domain"}):
        package = packages[name]
        require(package["source"] == {"registry": "https://pypi.org/simple"})
        candidates = []
        for wheel in package.get("wheels", []):
            url = urlsplit(wheel["url"])
            filename = url.path.rsplit("/", 1)[-1]
            require(url.scheme == "https" and url.netloc == "files.pythonhosted.org"
                    and not url.query and not url.fragment
                    and re.fullmatch(r"sha256:[0-9a-f]{64}", wheel["hash"])
                    and type(wheel["size"]) is int and 0 < wheel["size"] <= MAX_WHEEL)
            if compatible(filename):
                candidates.append((filename, wheel))
        require(candidates)
        filename, wheel = sorted(candidates)[0]
        require(filename not in selected)
        selected[filename] = {"name": name, "version": package["version"], **wheel}
    require(selected and sum(w["size"] for w in selected.values()) <= MAX_TOTAL)
    return selected


def expected(revision):
    files = review.committed_files(revision)
    lock_bytes = files["apps/api/uv.lock"]
    wheels = selected_wheels(tomllib.loads(lock_bytes.decode()))
    manifest = json.dumps({
        "schema": "agent-dependencies-v1", "revision": revision, "target": TARGET,
        "activation": "disabled", "lock_sha256": review.sha256(lock_bytes), "wheels": wheels,
    }, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    requirements = "".join(
        f"{wheel['name']}=={wheel['version']} --hash={wheel['hash']}\n"
        for wheel in wheels.values()).encode()
    return wheels, {"agent-dependencies.json": manifest, "requirements.txt": requirements}


def read_regular(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        item = os.fstat(stream.fileno())
        require(stat.S_ISREG(item.st_mode) and item.st_nlink == 1 and item.st_size <= limit)
        data = stream.read(limit + 1)
        require(len(data) == item.st_size)
        return data


def verify(directory, revision):
    wheels, metadata = expected(revision)
    require(stat.S_ISDIR(directory.lstat().st_mode))
    names = set()
    for path in directory.iterdir():
        names.add(path.name)
        require(len(names) <= len(wheels) + len(metadata))
    require(names == wheels.keys() | metadata.keys())
    for name, data in metadata.items():
        require(read_regular(directory / name, len(data)) == data)
    for name, wheel in wheels.items():
        data = read_regular(directory / name, wheel["size"])
        require(len(data) == wheel["size"] and "sha256:" + review.sha256(data) == wheel["hash"])
    return len(wheels)


def create(directory, revision):
    wheels, metadata = expected(revision)
    directory.mkdir()  # Never adopt/overwrite an existing destination, including symlinks.
    for name, wheel in wheels.items():
        with urlopen(wheel["url"], timeout=20) as response:
            require(response.geturl() == wheel["url"])
            data = response.read(wheel["size"] + 1)
        require(len(data) == wheel["size"] and "sha256:" + review.sha256(data) == wheel["hash"])
        with (directory / name).open("xb") as stream:
            stream.write(data)
    # No manifest/requirements are published for an incomplete download.
    for name, data in metadata.items():
        with (directory / name).open("xb") as stream:
            stream.write(data)
    return verify(directory, revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    try:
        count = (create if args.action == "create" else verify)(args.directory, args.revision)
        print(f"Verified {count} locked wheels for {TARGET}; activation disabled.")
    except Exception:
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
