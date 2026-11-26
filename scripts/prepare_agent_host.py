"""Prepare fresh locked identities and static synthetic units; never activate them."""

import argparse
import os
import stat
import subprocess
from pathlib import Path

from scripts import install_agent_inactive as runtime

ERROR = "Inactive agent host preparation unconfirmed; retain partial state for review"
UNITS = Path("/etc/systemd/system")
UNIT_PATHS = tuple(Path(p) for p in (
    "/etc/systemd/system.control", "/run/systemd/system.control",
    "/run/systemd/transient", "/run/systemd/generator.early",
    "/etc/systemd/system", "/etc/systemd/system.attached",
    "/run/systemd/system", "/run/systemd/system.attached", "/run/systemd/generator",
    "/usr/local/lib/systemd/system", "/usr/lib/systemd/system", "/lib/systemd/system",
    "/run/systemd/generator.late",
))
PRIVATE = (Path("/run/ciq-agent-claim"), Path("/run/ciq-agent-custody"),
           Path("/run/ciq-agent-receipts"), Path("/run/ciq-agent-supervisor"))


def require(value):
    if not value:
        raise ValueError(ERROR)


def protected(path, directory=True):
    info = path.lstat()
    require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            and info.st_uid == 0 and not info.st_mode & 0o7022)
    if not directory:
        require(info.st_nlink == 1)


def absent(path):
    require(not path.exists() and not path.is_symlink())


def fresh_units():
    """Refuse existing units, hierarchical drop-ins and boot dependency entries."""
    names = {f"ciq-agent-{role}.service" for role in runtime.ROLES}
    drops = {"service.d", "ciq-.service.d", "ciq-agent-.service.d",
             *(name + ".d" for name in names)}
    for parent in UNIT_PATHS:
        if not parent.exists() and not parent.is_symlink():
            continue
        # Debian's /lib is a trusted merged-/usr symlink. Check its actual
        # directory and every resolved ancestor without changing permissions.
        resolved = parent.resolve(strict=True)
        for path in (resolved, *resolved.parents):
            protected(path)
        for name in names | drops:
            absent(parent / name)
        children = list(parent.iterdir())
        require(len(children) <= 4096)
        for child in children:
            if child.is_symlink():
                require(Path(os.readlink(child)).name not in names)
            if child.name.endswith((".wants", ".requires", ".upholds")):
                require(not child.is_symlink())
                protected(child)
                for name in names:
                    absent(child / name)


def manager_inactive(missing=False):
    if Path("/proc/1/comm").read_text().strip() != "systemd":
        return  # Offline image preparation has no running system manager.
    for role in runtime.ROLES:
        result = run("/usr/bin/systemctl", "show", f"ciq-agent-{role}.service",
                     "--property=LoadState,ActiveState,SubState,MainPID,ControlPID,Job",
                     allowed=(0, 4))
        require(len(result.stdout) <= 1024)
        lines = result.stdout.decode().splitlines()
        fields = dict(line.split("=", 1) for line in lines)
        require(len(lines) == len(fields))
        require(set(fields) == {"LoadState", "ActiveState", "SubState", "MainPID",
                                "ControlPID", "Job"}
                and fields["LoadState"] in ({"not-found"} if missing else {"not-found", "loaded"})
                and fields["ActiveState"] == "inactive" and fields["SubState"] == "dead"
                and fields["MainPID"] == fields["ControlPID"] == "0" and fields["Job"] == "")


def preflight(revision, digest):
    runtime.host_guard()  # Unsupported/non-root hosts refuse before all input reads.
    runtime.inactive()  # Includes all account name/UID/GID collisions.
    for path in PRIVATE:
        absent(path)
    for path in (Path("/etc"), Path("/etc/systemd"), UNITS, runtime.INSTALL):
        protected(path)
    absent(runtime.INSTALL / "agent-host.json")
    absent(runtime.INSTALL / ".host-units")
    fresh_units()
    manager_inactive(missing=True)
    # Trust the installed tree only under the original trusted-root boundary.
    # Do not repair/adopt permissions or execute a writable installed import.
    for parent, directories, files in os.walk(runtime.INSTALL):
        for path in (Path(parent), *(Path(parent) / n for n in directories + files)):
            if path.is_symlink():
                require(path.resolve(strict=True).is_relative_to(runtime.INSTALL))
            else:
                protected(path, path.is_dir())
    _, pin, _ = runtime.python_bundle.expected(revision)
    expected = runtime.release.canonical({
        "schema": "agent-inactive-install-v1", "revision": revision,
        "wheel_manifest_sha256": digest, "python_sha256": pin["sha256"],
        "activation": "disabled",
    })
    require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest))
    require(runtime.release.dependencies.read_regular(
        runtime.INSTALL / "agent-install.json", 4096) == expected)
    runtime.installed(revision)
    source = runtime.release.review.committed_files(revision)
    return {f"ciq-agent-{role}.service": source[
        f"deploy/agent-controller/systemd/ciq-agent-{role}.service.example"]
        for role in runtime.ROLES}


def run(*args, allowed=(0,)):
    result = subprocess.run(args, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                            cwd="/", stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=15)
    require(result.returncode in allowed)  # Never expose arbitrary account/tool diagnostics.
    return result


def identities():
    import spwd  # Linux host Python 3.11 only; never imported on the operator Mac.

    for name, uid in runtime.ACCOUNTS:
        user, group = runtime.pwd.getpwnam(name), runtime.grp.getgrnam(name)
        require(user == runtime.pwd.getpwuid(uid) and user.pw_uid == user.pw_gid == uid
                and user.pw_dir == "/nonexistent" and user.pw_shell == "/usr/sbin/nologin"
                and group == runtime.grp.getgrgid(uid) and group.gr_gid == uid
                and not group.gr_mem and spwd.getspnam(name).sp_pwdp == "!")
        require(not any(name in g.gr_mem for g in runtime.grp.getgrall()))


def prepare(revision, digest):
    units = preflight(revision, digest)  # Complete read-only review before mutations.
    for name, uid in runtime.ACCOUNTS:
        run("/usr/sbin/groupadd", "--gid", str(uid), name)
        run("/usr/sbin/useradd", "--system", "--uid", str(uid), "--gid", str(uid),
            "--no-user-group", "--no-create-home", "--no-log-init",
            "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin", "--password", "!",
            "--key", "SUB_UID_COUNT=0",
            "--key", "SUB_GID_COUNT=0", name)
    identities()
    stage = runtime.INSTALL / ".host-units"
    stage.mkdir(mode=0o700)
    for name, data in units.items():
        with (stage / name).open("xb") as stream:
            stream.write(data)
        (stage / name).chmod(0o644)
    run("/usr/bin/systemd-analyze", "verify", "--man=no",
        *(str(stage / name) for name in units))
    fresh_units()  # No competing installer/drop-in may be adopted after analysis.
    for name, data in units.items():
        with (UNITS / name).open("xb") as stream:
            stream.write(data)
        (UNITS / name).chmod(0o644)
        protected(UNITS / name, False)
        require(runtime.release.dependencies.read_regular(UNITS / name, 8192) == data)
    identities()
    for path in PRIVATE:
        absent(path)
    manager_inactive()
    receipt = runtime.release.canonical({
        "schema": "agent-inactive-host-v1", "revision": revision,
        "wheel_manifest_sha256": digest, "activation": "disabled",
        "identities": dict(runtime.ACCOUNTS),
        "units": {name: runtime.release.review.sha256(data) for name, data in units.items()},
    })
    with (runtime.INSTALL / "agent-host.json").open("xb") as stream:
        stream.write(receipt)
    (runtime.INSTALL / "agent-host.json").chmod(0o644)
    # Keep reviewed staging bytes. Never reload/start/enable/unmask any unit,
    # create a plan/socket/journal, make grants, or delete partial host state.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        prepare(args.revision, args.manifest_sha256)
        print("Locked agent identities and static units prepared; activation remains disabled.")
    except Exception:
        raise SystemExit(ERROR) from None


if __name__ == "__main__":
    main()
