"""Disposable Debian 12 CI: offline runtime and fresh host setup, never activation."""

import os
import platform
import shutil
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
    paths = [*packages.policy.PLANS, Path("/run/ciq-agent-supervisor")]
    for parent in ("/etc/systemd/system", "/run/systemd/system",
                   "/usr/lib/systemd/system", "/lib/systemd/system"):
        paths.extend(Path(parent) / f"ciq-agent-{role}.service" for role in packages.policy.ROLES)
    require(not any(path.exists() or path.is_symlink() for path in paths))


def main():
    try:
        guard()  # Before downloads, builds, interpreter installation or writes.
        base = Path("/run") / ("ciq-debian-package-" + uuid4().hex[:16])
        base.mkdir(mode=0o755)
        packages.INSTALL.mkdir(mode=0o755)
        release_directory, revision, digest = packages.install(base)
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
        # Only the fixture's fresh identities/units; never an operator uninstall.
        for role in installer.ROLES:
            (host.UNITS / f"ciq-agent-{role}.service").unlink()
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
        frame, location = error.__traceback__, None
        while frame is not None:
            name = Path(frame.tb_frame.f_code.co_filename).name
            if name in {"test_agent_debian_package.py", "prepare_agent_host.py",
                        "install_agent_inactive.py"}:
                location = (name, frame.tb_lineno)
            frame = frame.tb_next
        if location:
            print(f"FAIL: inactive Debian preparation at {location[0]}:{location[1]}", flush=True)
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
