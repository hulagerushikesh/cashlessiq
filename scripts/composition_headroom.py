"""Explicit Linux admission for disposable integration, never capacity planning.

Fresh bounded Docker observations and bounded proc reads precede each resource
allocation. No cached PASS, configuration changes, process control or fallback
to the Mac policy. Docker CLI usage excludes cache; it is an estimate, not a
reservation. The trusted test owner must keep the host/daemon exclusive.
"""

import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .bounded_composition_actor import BoundedActor
from .check_product_host import GIB, _bytes

INFO = (
    "info",
    "--format",
    '{"memory":{{.MemTotal}},"cpus":{{.NCPU}},"running":{{.ContainersRunning}}}',
)
LIST = ("container", "ls", "--no-trunc", "--format", "{{.ID}}")
STATS = (
    "stats",
    "--no-stream",
    "--no-trunc",
    "--format",
    '{"id":"{{.ID}}","memory":"{{.MemUsage}}"}',
)
COMMANDS = (INFO, LIST, STATS)


class HeadroomDenied(ValueError):
    def __init__(self):
        super().__init__("Disposable Linux headroom admission denied")


def require(value):
    if not value:
        raise HeadroomDenied()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def memory(output):
    require(type(output) is str and 0 < len(output) <= 16384)
    expected = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    values = {}
    for line in output.splitlines():
        key = line.split(":", 1)[0]
        if key in expected:
            match = re.fullmatch(r"([A-Za-z]+):\s+([0-9]+) kB", line)
            require(match is not None and key not in values)
            # Linux /proc calls these kB, but their unit is 1024 bytes.
            values[key] = int(match[2]) * 1024
    require(set(values) == expected)
    require(0 <= values["MemAvailable"] <= values["MemTotal"] and values["MemTotal"] > 0)
    require(0 <= values["SwapFree"] <= values["SwapTotal"])
    return values


def pressure(output):
    require(type(output) is str and 0 < len(output) <= 1024)
    rows = {}
    for line in output.splitlines():
        match = re.fullmatch(
            r"(some|full) avg10=([0-9]+\.[0-9]+) avg60=([0-9]+\.[0-9]+) "
            r"avg300=([0-9]+\.[0-9]+) total=([0-9]+)",
            line,
        )
        require(match is not None and match[1] not in rows)
        values = tuple(float(value) for value in match.group(2, 3, 4))
        require(all(math.isfinite(value) and 0 <= value <= 100 for value in values))
        rows[match[1]] = values[0]
    require(set(rows) == {"some", "full"} and rows["full"] <= rows["some"])
    return rows


def identities(output):
    require(type(output) is str and len(output) <= 16384)
    rows = output.splitlines()
    require(len(rows) <= 128 and len(set(rows)) == len(rows))
    require(all(re.fullmatch("[0-9a-f]{64}", value) for value in rows))
    return frozenset(rows)


@dataclass(frozen=True)
class Snapshot:
    host_memory_bytes: int
    available_memory_bytes: int
    swap_used_bytes: int
    host_cpus: int
    load_one_minute: float
    memory_some_avg10: float
    memory_full_avg10: float
    disk_free_bytes: int
    docker_memory_bytes: int
    docker_cpus: int
    docker_used_bytes: int
    running_containers: int


def blockers(snapshot):
    require(type(snapshot) is Snapshot)
    reasons = []
    if snapshot.host_cpus < 2 or snapshot.docker_cpus < 2:
        reasons.append("fewer than two host/Docker CPUs")
    if snapshot.host_memory_bytes < 3 * GIB or snapshot.docker_memory_bytes < 3 * GIB:
        reasons.append("host/Docker memory below 3 GiB")
    if snapshot.available_memory_bytes < 2 * GIB:
        reasons.append("less than 2 GiB host available memory")
    if snapshot.docker_memory_bytes - snapshot.docker_used_bytes < 2 * GIB:
        reasons.append("less than 2 GiB estimated Docker memory headroom")
    if snapshot.load_one_minute > snapshot.host_cpus * 0.75:
        reasons.append("host load exceeds conservative test threshold")
    if snapshot.memory_some_avg10 > 5 or snapshot.memory_full_avg10 > 1:
        reasons.append("memory pressure exceeds conservative test threshold")
    if snapshot.disk_free_bytes < 12 * GIB:
        reasons.append("less than 12 GiB disk headroom")
    return tuple(reasons)


def proc(name, deadline_ns):
    require(name in {"meminfo", "loadavg", "pressure/memory"})
    budget = min(2_000_000_000, deadline_ns - time.monotonic_ns() - 2_000_000_000)
    value = BoundedActor(
        (
            sys.executable,
            "-I",
            str(Path(__file__).with_name("composition_engine.py").resolve()),
            "--command",
            "/bin/cat",
            "/proc/" + name,
        ),
        budget_ns=budget,
        grace_ns=300_000_000,
    ).execute()
    require(type(value) is dict and set(value) == {"output"})
    return value["output"]


class LinuxHeadroom:
    def __init__(self, engine, deadline_ns, disk_root):
        require(callable(engine) and type(deadline_ns) is int)
        require(isinstance(disk_root, Path) and disk_root.is_absolute())
        self.engine, self.deadline_ns, self.disk_root = engine, deadline_ns, disk_root
        self.last = None
        self.samples = 0

    def collect(self):
        require(sys.platform == "linux" and time.monotonic_ns() < self.deadline_ns)
        mem = memory(proc("meminfo", self.deadline_ns))
        psi = pressure(proc("pressure/memory", self.deadline_ns))
        load = proc("loadavg", self.deadline_ns)
        require(type(load) is str and len(load) <= 1024)
        fields = load.split()
        require(len(fields) == 5 and re.fullmatch(r"[0-9]+\.[0-9]+", fields[0]))
        load_one = float(fields[0])
        require(math.isfinite(load_one))
        cpus = len(os.sched_getaffinity(0))
        disk = os.statvfs(self.disk_root)
        info = json.loads(self.engine(*INFO), object_pairs_hook=unique)
        require(type(info) is dict and set(info) == {"memory", "cpus", "running"})
        require(all(type(value) is int and value >= 0 for value in info.values()))
        require(info["memory"] > 0 and info["cpus"] > 0)
        before = identities(self.engine(*LIST))
        require(len(before) == info["running"])
        used, seen = 0, set()
        if before:
            output = self.engine(*STATS)
            require(type(output) is str and len(output) <= 32768)
            for line in output.splitlines():
                row = json.loads(line, object_pairs_hook=unique)
                require(type(row) is dict and set(row) == {"id", "memory"})
                require(type(row["id"]) is str and row["id"] in before and row["id"] not in seen)
                require(type(row["memory"]) is str)
                parts = row["memory"].split(" / ")
                require(len(parts) == 2)
                amount, limit = map(_bytes, parts)
                require(0 <= amount <= limit <= info["memory"])
                used += amount
                seen.add(row["id"])
        require(seen == set(before) and identities(self.engine(*LIST)) == before)
        require(used <= info["memory"] and time.monotonic_ns() < self.deadline_ns)
        return Snapshot(
            mem["MemTotal"],
            mem["MemAvailable"],
            mem["SwapTotal"] - mem["SwapFree"],
            cpus,
            load_one,
            psi["some"],
            psi["full"],
            disk.f_bavail * disk.f_frsize,
            info["memory"],
            info["cpus"],
            used,
            len(before),
        )

    def __call__(self):
        # Last success is diagnostic only and is cleared before every attempt.
        self.last = None
        try:
            sample = self.collect()
            require(not blockers(sample))
            self.last = sample
            self.samples += 1
            return True
        except Exception:
            raise HeadroomDenied() from None
