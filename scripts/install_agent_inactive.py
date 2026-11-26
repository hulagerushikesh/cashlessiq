"""Install verified offline artifacts on a fresh Debian 12 host; activate nothing."""

import argparse
import grp
import io
import os
import platform
import pwd
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

from scripts import package_agent_python as python_bundle

release = python_bundle.release
INSTALL = Path("/opt/cashlessiq-agent")
ROLES = ("claim", "custody", "receipt")
ACCOUNTS = (("ciq-agent-clinical", 53001), ("ciq-agent-custody", 53002),
            ("ciq-agent-receipt", 53003))
ERROR = "Inactive agent installation unconfirmed; retain partial output for review"
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PIP_CONFIG_FILE": "/dev/null"}


def require(value):
    if not value:
        raise ValueError(ERROR)


def inactive():
    for name, uid in ACCOUNTS:
        for lookup, key in ((pwd.getpwnam, name), (pwd.getpwuid, uid),
                            (grp.getgrnam, name), (grp.getgrgid, uid)):
            try:
                lookup(key)
            except KeyError:
                continue
            raise ValueError(ERROR)
    paths = [*(Path("/run") / ("ciq-agent-" + role) for role in ROLES),
             Path("/run/ciq-agent-supervisor")]
    for parent in ("/etc/systemd/system", "/run/systemd/system",
                   "/usr/lib/systemd/system", "/lib/systemd/system"):
        paths.extend(Path(parent) / f"ciq-agent-{role}.service" for role in ROLES)
    require(not any(path.exists() or path.is_symlink() for path in paths))


def guard():
    require(sys.platform == "linux" and os.geteuid() == 0 and hasattr(tarfile, "data_filter"))
    system = platform.freedesktop_os_release()
    require(system.get("ID") == "debian" and system.get("VERSION_ID") == "12"
            and platform.machine() == "x86_64" and platform.libc_ver() == ("glibc", "2.36"))
    for path in (Path("/"), INSTALL.parent):
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022)
    require(not INSTALL.exists() and not INSTALL.is_symlink())
    inactive()


def unpack(data, destination):
    """Only the already hash-verified archive reaches this fresh owned directory."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members, names, total = [], set(), 0
        for member in archive:
            path = PurePosixPath(member.name)
            require(len(members) < 6000 and not path.is_absolute()
                    and path.parts and path.parts[0] == "python"
                    and ".." not in path.parts and str(path) == member.name.rstrip("/")
                    and str(path) not in names
                    and (member.isfile() or member.isdir() or member.issym())
                    and 0 <= member.size <= 32_000_000)
            total += member.size
            require(total <= 128_000_000)
            names.add(str(path))
            members.append(member)
        # data_filter additionally checks link destinations and extraction paths
        # against the actual filesystem. No pre-existing tree may be adopted.
        archive.extractall(destination, members=members, filter="data")


def run(python, *args, timeout=120):
    result = subprocess.run([str(python), "-I", "-B", *args], env=ENV,
                            cwd="/", stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=timeout)
    require(result.returncode == 0)  # Never expose arbitrary installer diagnostics.


PIP = """
import ensurepip, runpy, sys
from pathlib import Path
wheel = Path(ensurepip.__file__).parent / '_bundled/pip-24.0-py3-none-any.whl'
if not wheel.is_file() or not wheel.is_relative_to(Path(sys.base_prefix)): sys.exit(20)
sys.path.insert(0, str(wheel))
sys.argv = ['pip', '--isolated', '--disable-pip-version-check', *sys.argv[1:]]
runpy.run_module('pip', run_name='__main__')
"""


def harden(root):
    for parent, directories, files in os.walk(root):
        for path in (Path(parent), *(Path(parent) / n for n in directories + files)):
            item = path.lstat()
            require(item.st_uid == 0)
            if stat.S_ISLNK(item.st_mode):
                require(path.resolve(strict=True).is_relative_to(root))
            else:
                require(stat.S_ISREG(item.st_mode) or stat.S_ISDIR(item.st_mode))
                path.chmod(stat.S_IMODE(item.st_mode) & ~0o7022)


def installed(revision):
    packages = release.first_party(release.review.committed_files(revision))
    site = INSTALL / "venv/lib/python3.11/site-packages"
    for _, _, code in packages.values():
        for name, expected in code.items():
            require(release.dependencies.read_regular(site / name, len(expected)) == expected)
    run(INSTALL / "venv/bin/python", "-c", """
import importlib.util, sys
import ciq_api.agent_claim_runner, ciq_api.agent_custody_runner, ciq_api.agent_receipt_runner
import cashlessiq_domain
if sys.version_info[:3] != (3, 11, 15): sys.exit(21)
if any(importlib.util.find_spec(n) is not None for n in
       ('pip', 'setuptools', 'hatchling', 'snowflake', 'pytest', 'cashlessiq')): sys.exit(22)
""")


def install(wheels, interpreter, revision, digest):
    guard()  # Before input reads, subprocesses or host mutation.
    wheels, interpreter = wheels.absolute(), interpreter.absolute()
    verified = release.verified_files(wheels, revision, digest)
    archive = python_bundle.verify(interpreter, revision)
    data = release.dependencies.read_regular(archive, python_bundle.MAX_ARCHIVE)
    _, pin, _ = python_bundle.expected(revision)
    require(release.review.sha256(data) == pin["sha256"])
    INSTALL.mkdir(mode=0o755)  # Fresh root-owned parent; never repair or overwrite.
    snapshot = INSTALL / ".bootstrap-wheels"
    snapshot.mkdir(mode=0o700)
    for name, value in verified.items():
        if name.endswith(".whl") or name == "requirements.txt":
            with (snapshot / name).open("xb") as stream:
                stream.write(value)
    del verified
    unpack(data, INSTALL)
    del data
    run(INSTALL / "python/bin/python3.11", "-m", "venv", "--without-pip", str(INSTALL / "venv"))
    python = INSTALL / "venv/bin/python"
    # Use pip directly from the pinned interpreter archive. It is not installed
    # into the service venv. /dev/null disables global/site config as well as
    # --isolated ignoring user configuration and the caller's environment.
    run(python, "-c", PIP, "install", "--no-index", "--no-cache-dir", "--no-deps",
        "--require-hashes", "--only-binary=:all:", "--no-compile",
        "--find-links", str(snapshot), "--requirement", str(snapshot / "requirements.txt"))
    run(python, "-c", PIP, "check")
    shutil.rmtree(snapshot)  # Only this invocation's private, public-byte snapshot.
    harden(INSTALL)
    installed(revision)
    inactive()
    receipt = release.canonical({"schema": "agent-inactive-install-v1", "revision": revision,
                                 "wheel_manifest_sha256": digest,
                                 "python_sha256": pin["sha256"], "activation": "disabled"})
    with (INSTALL / "agent-install.json").open("xb") as stream:
        stream.write(receipt)
    (INSTALL / "agent-install.json").chmod(0o644)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheels", required=True, type=Path)
    parser.add_argument("--interpreter", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        install(args.wheels, args.interpreter, args.revision, args.manifest_sha256)
        print("Verified offline inactive installation; no identities, units or authority created.")
    except Exception:
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
