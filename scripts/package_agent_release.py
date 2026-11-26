"""Assemble/verify public offline runtime wheels; never build, install or activate."""

import argparse
import base64
import csv
import io
import json
import re
import stat
import tomllib
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

from scripts import package_agent_dependencies as dependencies
from scripts.check_domain_package import MODULES

review = dependencies.review
MANIFEST = "agent-release.json"
SOURCE = "agent-review.tar.gz"
MAX_FIRST_PARTY = 4_000_000
MAX_METADATA = 32_000
ERROR = "Agent wheel release unconfirmed"


def require(value):
    if not value:
        raise ValueError(ERROR)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def inventory(directory, expected):
    require(stat.S_ISDIR(directory.lstat().st_mode))
    names = set()
    for path in directory.iterdir():
        names.add(path.name)
        require(len(names) <= len(expected))
    require(names == expected)


def first_party(files):
    """Derive every executable/resource byte and package identity from Git."""
    packages = {}
    for project, module in (("apps/api", "ciq_api"), ("packages/domain", "cashlessiq_domain")):
        metadata = tomllib.loads(files[project + "/pyproject.toml"].decode())["project"]
        name, version = metadata["name"], metadata["version"]
        require(re.fullmatch(r"[a-z][a-z0-9-]+", name)
                and re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}", version))
        prefix = f"{project}/src/{module}/"
        code = {module + "/" + path.removeprefix(prefix): data
                for path, data in files.items() if path.startswith(prefix)}
        if module == "cashlessiq_domain":
            code.update({f"{module}/{item}.py": files[f"src/cashlessiq/{item}.py"]
                         for item in MODULES})
        require(code and module + "/__init__.py" in code)
        stem = name.replace("-", "_") + "-" + version
        packages[stem + "-py3-none-any.whl"] = (stem + ".dist-info/", metadata, code)
    return packages


def verify_first_party(data, expected):
    """Inspect bounded ZIP members, without extracting or executing incoming code.

    Only source-matched package files and the three inert wheel metadata files
    are admitted. Requirements are derived separately from Git; installation
    must disable dependency resolution and use the entire hash-locked wheel set.
    """
    prefix, project, code = expected
    names = code.keys() | {prefix + name for name in ("METADATA", "WHEEL", "RECORD")}
    require(len(data) <= MAX_FIRST_PARTY)
    with ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        require(len(entries) == len(names) and {item.filename for item in entries} == names)
        require(sum(item.file_size for item in entries) <= review.MAX_TOTAL)
        contents = {}
        for item in entries:
            require(not item.flag_bits & 1 and item.file_size <= review.MAX_FILE
                    and stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG))
            contents[item.filename] = archive.read(item)
        require(all(contents[name] == value for name, value in code.items()))
        for name in ("METADATA", "WHEEL", "RECORD"):
            require(len(contents[prefix + name]) <= MAX_METADATA)
        metadata = Parser().parsestr(contents[prefix + "METADATA"].decode())
        for key, value in (("Name", project["name"]), ("Version", project["version"])):
            require(metadata.get_all(key) == [value])
        # Wheel metadata may order equivalent version constraints differently.
        require(len(metadata.get_all("Requires-Python", [])) == 1
                and sorted(metadata["Requires-Python"].split(","))
                == sorted(project["requires-python"].split(",")))
        wheel = Parser().parsestr(contents[prefix + "WHEEL"].decode())
        for key, value in (("Wheel-Version", "1.0"), ("Root-Is-Purelib", "true"),
                           ("Tag", "py3-none-any")):
            require(wheel.get_all(key) == [value])
        rows = list(csv.reader(io.StringIO(contents[prefix + "RECORD"].decode())))
        require(len(rows) == len(names) and all(len(row) == 3 for row in rows)
                and {row[0] for row in rows} == names)
        for name, digest, size in rows:
            if name == prefix + "RECORD":
                require(digest == size == "")
            else:
                value = contents[name]
                encoded = base64.urlsafe_b64encode(bytes.fromhex(review.sha256(value)))
                require(digest == "sha256=" + encoded.decode().rstrip("=")
                        and size == str(len(value)))


def payload(revision, dist, wheelhouse):
    """Read only fixed public artifacts; no directory recursion or network access."""
    files = review.committed_files(revision)
    packages = first_party(files)
    inventory(dist, packages.keys())
    dependencies.verify(wheelhouse, revision)
    wheels, _ = dependencies.expected(revision)
    result = {}
    for name, expected in packages.items():
        data = dependencies.read_regular(dist / name, MAX_FIRST_PARTY)
        verify_first_party(data, expected)
        result[name] = data
    for name, wheel in wheels.items():
        data = dependencies.read_regular(wheelhouse / name, wheel["size"])
        require(len(data) == wheel["size"] and "sha256:" + review.sha256(data) == wheel["hash"])
        result[name] = data
    result[SOURCE] = review.encode(revision, files)
    result["requirements.txt"] = requirements(packages, wheels, result)
    return result


def requirements(packages, wheels, files):
    # Every wheel is explicit: do not let metadata choose another dependency or
    # obtain an optional provider. The install command must include --no-deps.
    pins = {name: (project["name"], project["version"])
            for name, (_, project, _) in packages.items()}
    pins.update({name: (wheel["name"], wheel["version"]) for name, wheel in wheels.items()})
    return "".join(
        f"{name}=={version} --hash=sha256:{review.sha256(files[filename])}\n"
        for filename, (name, version) in sorted(pins.items())).encode()


def manifest(revision, files):
    return canonical({
        "schema": "agent-wheel-release-v1", "revision": revision,
        "target": dependencies.TARGET, "activation": "disabled",
        "files": {name: {"sha256": review.sha256(data), "size": len(data)}
                  for name, data in files.items()},
    })


def verify(directory, revision, manifest_sha256):
    """The digest must come from the reviewed build receipt, not this directory."""
    require(type(manifest_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", manifest_sha256))
    files = review.committed_files(revision)
    packages = first_party(files)
    wheels, _ = dependencies.expected(revision)
    names = packages.keys() | wheels.keys() | {MANIFEST, SOURCE, "requirements.txt"}
    inventory(directory, names)
    raw = dependencies.read_regular(directory / MANIFEST, MAX_METADATA)
    require(review.sha256(raw) == manifest_sha256)
    # Never use incoming self-reported hashes, sizes or names to select inputs.
    expected = {}
    for name in names - {MANIFEST}:
        limit = (review.MAX_COMPRESSED if name == SOURCE else MAX_METADATA
                 if name == "requirements.txt" else MAX_FIRST_PARTY
                 if name in packages else wheels[name]["size"])
        expected[name] = dependencies.read_regular(directory / name, limit)
    require(raw == manifest(revision, expected))
    review.verify_data(expected[SOURCE], revision, files)
    for name, package in packages.items():
        verify_first_party(expected[name], package)
    for name, wheel in wheels.items():
        require(len(expected[name]) == wheel["size"]
                and "sha256:" + review.sha256(expected[name]) == wheel["hash"])
    require(expected["requirements.txt"] == requirements(packages, wheels, expected))
    return len(packages) + len(wheels)


def create(directory, revision, dist, wheelhouse):
    files = payload(revision, dist, wheelhouse)  # Validate before creating output.
    raw = manifest(revision, files)
    directory.mkdir()  # Fresh caller-controlled parent; never adopt or overwrite.
    for name, data in sorted(files.items()):
        with (directory / name).open("xb") as stream:
            stream.write(data)
    with (directory / MANIFEST).open("xb") as stream:  # Completion marker last.
        stream.write(raw)
    digest = review.sha256(raw)
    return digest, verify(directory, revision, digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--dist", type=Path)
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    if args.action == "create":
        if args.dist is None or args.wheelhouse is None or args.manifest_sha256 is not None:
            parser.error("create requires --dist and --wheelhouse only")
    elif args.manifest_sha256 is None or args.dist is not None or args.wheelhouse is not None:
        parser.error("verify requires --manifest-sha256 only")
    try:
        if args.action == "create":
            digest, count = create(args.directory, args.revision, args.dist, args.wheelhouse)
        else:
            digest = args.manifest_sha256
            count = verify(args.directory, args.revision, digest)
        print(f"Verified {count} offline runtime wheels; manifest SHA-256 {digest}; "
              "activation disabled.")
    except Exception:
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
