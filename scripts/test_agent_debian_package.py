"""Disposable Debian 12 CI: offline runtime and fresh host setup, never activation."""

import hashlib
import os
import platform
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from scripts import install_agent_inactive as installer
from scripts import prepare_agent_host as host
from scripts import test_agent_service_packages as packages

ERROR = "Inactive Debian agent installation unconfirmed"


def require(value):
    if not value:
        raise ValueError(ERROR)


def guard():
    # A separate container job, never a way to bypass the systemd fixture guard
    # on an operator machine. It never starts services or creates private plans.
    require(sys.platform == "linux" and os.geteuid() == 0
            and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_REPOSITORY") == "hulagerushikesh/cashlessiq"
            and os.environ.get("CIQ_AGENT_DEBIAN_PACKAGE_TEST") == "1")
    release = platform.freedesktop_os_release()
    require(release.get("ID") == "debian" and release.get("VERSION_ID") == "12"
            and platform.machine() == "x86_64" and platform.libc_ver() == ("glibc", "2.36"))
    require(Path("/proc/1/comm").read_text().strip() != "systemd")
    require(not packages.INSTALL.exists() and not packages.INSTALL.is_symlink())
    verify_inactive()


def verify_inactive():
    for name, uid in packages.ACCOUNTS:
        for lookup, key in ((packages.pwd.getpwnam, name), (packages.pwd.getpwuid, uid),
                            (packages.policy.grp.getgrnam, name),
                            (packages.policy.grp.getgrgid, uid)):
            try:
                lookup(key)
            except KeyError:
                continue
            raise ValueError(ERROR)
    paths = [*packages.policy.PLANS, Path("/run/ciq-agent-supervisor"), installer.STORAGE]
    for parent in ("/etc/systemd/system", "/run/systemd/system",
                   "/usr/lib/systemd/system", "/lib/systemd/system"):
        paths.extend(Path(parent) / f"ciq-agent-{role}.service" for role in packages.policy.ROLES)
    require(not any(path.exists() or path.is_symlink() for path in paths))


def native_rehearsal(base, revision):
    """Guarded caller's fresh Debian CI base only; never install or allocate."""
    source_name = "deploy/agent-controller/native/single-call-launch.c"
    raw = packages.release.review.committed_files(revision)[source_name]
    directory = base / "native"
    directory.mkdir(mode=0o700)  # Never reuse or adopt an incoming build directory.
    source, binary = directory / "launch.c", directory / "launch"
    with source.open("xb") as stream:
        stream.write(raw)
    result = subprocess.run(
        ["/usr/bin/gcc-12", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
         "-Wconversion", "-fstack-protector-strong", "-D_FORTIFY_SOURCE=2",
         "-fPIE", "-pie", "-Wl,-z,relro,-z,now", str(source), "-o", str(binary)],
        cwd=directory, env={"PATH": "/usr/bin:/bin", "LANG": "C"},
        capture_output=True, timeout=20,
    )
    require(result.returncode == 0)
    payload = binary.read_bytes()
    require(64 <= len(payload) <= 1_000_000 and payload[:7] == b"\x7fELF\x02\x01\x01"
            and struct.unpack_from("<HH", payload, 16) == (3, 62))  # PIE, x86-64.
    require(not binary.is_symlink() and binary.stat().st_mode & 0o7022 == 0)
    # No arguments reaches the bootstrap's first deny, BEFORE clone, runtime,
    # cgroup, credential or identity inspection. This tests the target loader.
    refused = subprocess.run([str(binary)], cwd="/", env={"LANG": "C.UTF-8"},
                             capture_output=True, timeout=3)
    require(refused.returncode == 125 and refused.stdout == b""
            and refused.stderr == b"single_call_launch_unavailable\n")
    print(f"PASS: Debian 12 native bootstrap; revision {revision}; "
          f"source SHA-256 {hashlib.sha256(raw).hexdigest()}; "
          f"ELF SHA-256 {hashlib.sha256(payload).hexdigest()}")
    print("PASS: target native loader refuses missing arguments before any allocation")
    # The binary stays in this disposable base and is removed with it. A build
    # receipt is not an independently trusted release or installation authority.


def main():
    try:
        guard()  # Before downloads, builds, interpreter installation or writes.
        base = Path("/run") / ("ciq-debian-package-" + uuid4().hex[:16])
        base.mkdir(mode=0o755)
        packages.INSTALL.mkdir(mode=0o755)
        release_directory, revision, digest = packages.install(base)
        native_rehearsal(base, revision)
        verify_inactive()
        print("PASS: Debian 12/glibc 2.36 artifacts installed without agent identities or units")
        # Export only the already verified public wheel release, never the
        # private interpreter, builder, service inputs or arbitrary output tree.
        output = packages.policy.ROOT / "output/agent-release"
        output.parent.mkdir(exist_ok=True)
        shutil.copytree(release_directory, output)  # Refuse an existing destination.
        packages.release.verify(output, revision, digest)
        print("PASS: verified public wheel release exported without activation inputs")
        python_output = output.parent / "agent-python"
        shutil.copytree(base / "python-bundle", python_output)
        packages.python_bundle.verify(python_output, revision)
        print("PASS: pinned public interpreter archive exported without local paths")
        shutil.rmtree(packages.INSTALL)
        installer.install(output, python_output, revision, digest)
        verify_inactive()
        print("PASS: inactive host installer consumed only offline verified artifacts")
        host.prepare(revision, digest)
        host.identities()
        for role in installer.ROLES:
            unit = host.UNITS / f"ciq-agent-{role}.service"
            source = packages.release.review.committed_files(revision)[
                f"deploy/agent-controller/systemd/ciq-agent-{role}.service.example"]
            require(unit.read_bytes() == source)
        try:
            host.prepare(revision, digest)
        except ValueError:
            pass
        else:
            raise ValueError(ERROR)
        print("PASS: fresh Debian locked identities and static units prepared without activation")
        info = (installer.STORAGE / "receipts").lstat()
        require(info.st_uid == info.st_gid == installer.ACCOUNTS[2][1]
                and info.st_mode & 0o7777 == 0o700
                and not any((installer.STORAGE / "receipts").iterdir()))
        require(not (installer.STORAGE / "receipts/retained").exists())
        print("PASS: fresh persistent receipt namespace prepared without journal authority")
        # Only the fixture's fresh identities/units; never an operator uninstall.
        for role in installer.ROLES:
            (host.UNITS / f"ciq-agent-{role}.service").unlink()
        shutil.rmtree(installer.STORAGE)  # Only this fresh empty CI fixture.
        for name, _uid in reversed(installer.ACCOUNTS):
            host.run("/usr/sbin/userdel", name)
            host.run("/usr/sbin/groupdel", name, allowed=(0, 6))  # userdel may remove its group.
        verify_inactive()
        # These are fresh invocation-owned directories. No services were launched,
        # no database was contacted, and no private credential/receipt was made.
        shutil.rmtree(packages.INSTALL)
        shutil.rmtree(base)
        require(not packages.INSTALL.exists() and not base.exists())
        print("PASS: inactive Debian artifact installation removed")
    except Exception as error:
        # The isolated job container is discarded on failure too. Never print
        # arbitrary subprocess diagnostics or attempt to adopt/repair a runtime.
        # A fixed source location permits diagnosis without exception values,
        # account/tool output, file contents or interpreter frame locals.
        frame, locations = error.__traceback__, []
        while frame is not None:
            name = Path(frame.tb_frame.f_code.co_filename).name
            if name in {"test_agent_debian_package.py", "prepare_agent_host.py",
                        "install_agent_inactive.py"}:
                locations.append((name, frame.tb_lineno))
            frame = frame.tb_next
        for location in locations[-8:]:
            print(f"FAIL: inactive Debian preparation at {location[0]}:{location[1]}", flush=True)
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
