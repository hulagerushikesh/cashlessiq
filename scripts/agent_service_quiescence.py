"""Read-only stopped-service evidence; never a cleanup or credential authority.

The trusted caller must exclude concurrent activation/DDL and pin the installed
units and identities separately. A successful observation cannot lock the host,
authorize UID reuse or prove that no other process uses the service account.
"""

import os
import re
import subprocess
import sys

ERROR = "Agent service quiescence unconfirmed; private state must be retained"
FIELDS = (
    "Id", "LoadState", "ActiveState", "SubState", "MainPID", "ControlPID", "Job",
    "ControlGroup", "InvocationID", "NRestarts", "KillMode", "Restart",
)
CGROUP = "/sys/fs/cgroup/system.slice"


def require(value):
    if not value:
        raise ValueError(ERROR)


def snapshot(unit):
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", "--all", "--no-pager",
         "--property=" + ",".join(FIELDS), "--", unit],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    require(result.returncode == 0 and not result.stderr and len(result.stdout) <= 8192)
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        require(separator and key in FIELDS and key not in values)
        values[key] = value
    require(set(values) == set(FIELDS))
    require(values["Id"] == unit and values["LoadState"] == "loaded")
    require((values["ActiveState"], values["SubState"]) in {
        ("inactive", "dead"), ("failed", "failed"),
    })
    require(all(values[key] == "0" for key in ("MainPID", "ControlPID", "NRestarts")))
    require(values["Job"] == "" and values["Restart"] == "no"
            and values["KillMode"] == "control-group")
    require(values["ControlGroup"] in ("", "/system.slice/" + unit))
    require(values["InvocationID"] == ""
            or re.fullmatch("[0-9a-f]{32}", values["InvocationID"]))
    return values


def empty_group(unit):
    # Inspect the expected group even when systemd reports an empty ControlGroup.
    # Only absence of the group itself is retired evidence. Missing/unreadable
    # events inside an existing group must never be interpreted as empty.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parent = os.open(CGROUP, flags)
    try:
        try:
            group = os.open(unit, flags, dir_fd=parent)
        except FileNotFoundError:
            return
        try:
            events = os.open("cgroup.events", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=group)
            try:
                raw = os.read(events, 4097)
                require(len(raw) <= 4096)
            finally:
                os.close(events)
            records = [line.split() for line in raw.decode("ascii").splitlines()]
            require(records and all(len(record) == 2 for record in records))
            require(len({key for key, _ in records}) == len(records))
            require(dict(records).get("populated") == "0")
        finally:
            os.close(group)
    finally:
        os.close(parent)


def verify_stopped(unit):
    """Observe one trusted system.slice unit without stopping, resetting or deleting."""
    try:
        require(sys.platform == "linux" and os.geteuid() == 0)
        require(type(unit) is str and len(unit) <= 200
                and re.fullmatch(r"[a-z][a-z0-9-]*\.service", unit))
        before = snapshot(unit)
        empty_group(unit)
        require(snapshot(unit) == before)
    except Exception:
        # No unit values, cgroup contents or subprocess errors in public output.
        raise ValueError(ERROR) from None
