"""Read-only Mac/Docker headroom check; not a health provider or load guarantee.

No Docker builds, service control, credential/config inspection or host changes.
The future composition runner must call require_headroom before allocations and
between stages; this standalone check does not supervise an existing workload.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3


@dataclass(frozen=True)
class Snapshot:
    host_memory_bytes: int
    host_cpus: int
    pressure_level: int
    swap_used_bytes: int
    load_one_minute: float
    disk_free_bytes: int
    docker_memory_bytes: int
    docker_cpus: int
    docker_used_bytes: int
    running_containers: int


def _bytes(value: str) -> int:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(B|KiB|MiB|GiB|TiB|kB|MB|GB|TB|M)", value)
    if match is None:
        raise ValueError("Unknown resource unit")
    units = {
        "B": 1,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": GIB,
        "TiB": 1024**4,
        "kB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "M": 1024**2,  # macOS sysctl vm.swapusage
    }
    return int((Decimal(match[1]) * units[match[2]]).to_integral_value(rounding="ROUND_CEILING"))


def _read(*command: str) -> str:
    return subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=4
    ).stdout.strip()


def collect() -> Snapshot:
    if sys.platform != "darwin":
        raise ValueError("This headroom check is Mac-only")
    values = _read(
        "sysctl", "-n", "hw.memsize", "hw.ncpu", "kern.memorystatus_vm_pressure_level"
    ).splitlines()
    if len(values) != 3 or any(not re.fullmatch(r"[0-9]+", value) for value in values):
        raise ValueError("Invalid Mac resource observation")
    swap = re.search(r"\bused\s*=\s*([0-9]+(?:\.[0-9]+)?M)\b", _read("sysctl", "vm.swapusage"))
    if swap is None:
        raise ValueError("Unknown swap observation")
    # Select metrics only: never dump docker info/inspect or container environments.
    info = json.loads(
        _read(
            "docker",
            "info",
            "--format",
            '{"memory":{{.MemTotal}},"cpus":{{.NCPU}},"running":{{.ContainersRunning}}}',
        )
    )
    if set(info) != {"memory", "cpus", "running"} or any(
        type(value) is not int or value < 0 for value in info.values()
    ):
        raise ValueError("Invalid Docker resource observation")
    stats = _read("docker", "stats", "--no-stream", "--format", "{{.MemUsage}}")
    rows = stats.splitlines() if stats else []
    if len(rows) != info["running"]:
        raise ValueError("Docker inventory changed during observation")
    used = 0
    for row in rows:
        parts = row.split(" / ")
        if len(parts) != 2:
            raise ValueError("Unknown Docker memory observation")
        used += _bytes(parts[0])
        _bytes(parts[1])
    return Snapshot(
        host_memory_bytes=int(values[0]),
        host_cpus=int(values[1]),
        pressure_level=int(values[2]),
        swap_used_bytes=_bytes(swap[1]),
        load_one_minute=os.getloadavg()[0],
        disk_free_bytes=shutil.disk_usage(ROOT).free,
        docker_memory_bytes=info["memory"],
        docker_cpus=info["cpus"],
        docker_used_bytes=used,
        running_containers=info["running"],
    )


def blockers(snapshot: Snapshot) -> tuple[str, ...]:
    """Conservative local test policy, not production capacity planning."""
    reasons = []
    if snapshot.pressure_level != 1:
        reasons.append("Mac memory pressure is not normal (1); defer heavy acceptance")
    if snapshot.host_memory_bytes < 8 * GIB:
        reasons.append("Less than 8 GiB host memory")
    if snapshot.host_cpus < 2 or snapshot.docker_cpus < 2:
        reasons.append("Fewer than two host/Docker CPUs")
    if snapshot.load_one_minute > snapshot.host_cpus * 0.75:
        reasons.append("Host load exceeds conservative test threshold")
    if snapshot.disk_free_bytes < 12 * GIB:
        reasons.append("Less than 12 GiB disk headroom")
    if snapshot.docker_memory_bytes < 3 * GIB:
        reasons.append("Docker memory allocation is below 3 GiB; do not auto-increase it")
    if snapshot.docker_memory_bytes - snapshot.docker_used_bytes < 2 * GIB:
        reasons.append("Less than 2 GiB estimated Docker memory headroom")
    return tuple(reasons)


def require_headroom() -> Snapshot:
    snapshot = collect()
    reasons = blockers(snapshot)
    if reasons:
        raise RuntimeError("; ".join(reasons))
    return snapshot


def main() -> int:
    try:
        snapshot = collect()
        reasons = blockers(snapshot)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print("DEFER: resource observation unavailable/invalid; no heavy run authorized")
        return 2
    print(json.dumps(asdict(snapshot), sort_keys=True))
    for reason in reasons:
        print(f"DEFER: {reason}")
    if snapshot.swap_used_bytes > snapshot.host_memory_bytes // 2:
        print("NOTE: substantial swap is allocated; this alone is not current swap activity")
    print(
        "DEFER: no containers created; leave existing applications/settings untouched"
        if reasons
        else "PASS: sampled preflight only; recheck between stages, no safety/SLA guarantee"
    )
    return 2 if reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
