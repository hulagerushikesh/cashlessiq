"""Sample preview memory while a command runs, optionally including its Linux host."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

PREFIX = "cashlessiq-owner-preview-"
SERVICES = ("db", "api", "web", "gateway")
MEMORY = re.compile(r"^(\d+(?:\.\d+)?)(B|KiB|MiB|GiB|TiB)\b")
SCALE = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "TiB": 1024**2}
HOST_FIELDS = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}


def parse_host_memory(output: str) -> dict[str, float]:
    """Read Linux's available-memory estimate, including reclaimable cache."""
    counters = {}
    for line in output.splitlines():
        key, separator, value = line.partition(":")
        if key not in HOST_FIELDS:
            continue
        parts = value.split()
        if (
            not separator
            or key in counters
            or len(parts) != 2
            or not parts[0].isdigit()
            or parts[1] != "kB"
        ):
            raise ValueError("Malformed Linux host memory counters")
        counters[key] = int(parts[0]) / 1024
    if set(counters) != HOST_FIELDS:
        raise ValueError("Linux host memory counters are missing")
    if (
        counters["MemTotal"] <= 0
        or counters["MemAvailable"] > counters["MemTotal"]
        or counters["SwapFree"] > counters["SwapTotal"]
    ):
        raise ValueError("Inconsistent Linux host memory counters")
    return {
        "total_mib": counters["MemTotal"],
        "available_mib": counters["MemAvailable"],
        "swap_used_mib": counters["SwapTotal"] - counters["SwapFree"],
    }


def parse_stats(output: str) -> dict[str, float]:
    """Read the current usage, not the limit, for this preview's steady services."""
    usage = {}
    for line in output.splitlines():
        name, separator, memory = line.partition("\t")
        if not separator or not name.startswith(PREFIX):
            continue
        service = name[len(PREFIX) :].rsplit("-", 1)[0]
        if service not in SERVICES:
            continue
        match = MEMORY.match(memory)
        if not match:
            raise ValueError(f"Unrecognized Docker memory usage for {service}: {memory}")
        usage[service] = float(match[1]) * SCALE[match[2]]
    return usage


def sample(
    command: list[str],
    *,
    interval: float = 3,
    read_stats: Callable[[], str] | None = None,
    include_host: bool = False,
    read_host_memory: Callable[[], str] | None = None,
) -> int:
    """Preserve the command result and print sampled memory highs for review."""
    if read_stats is None:

        def read_stats() -> str:
            return subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=8,
            ).stdout

    host_baseline = None
    if include_host:
        if read_host_memory is None:

            def read_host_memory() -> str:
                return Path("/proc/meminfo").read_text()

        try:
            host_baseline = parse_host_memory(read_host_memory())
        except (OSError, ValueError):
            print("Linux host memory unavailable; command was not started.", file=sys.stderr)
            return 1
    host_minimum_available = host_baseline["available_mib"] if host_baseline else 0
    host_maximum_swap = host_baseline["swap_used_mib"] if host_baseline else 0

    stop = threading.Event()
    peaks: dict[str, float] = {}
    sample_count = 0
    error: Exception | None = None

    def observe() -> None:
        nonlocal sample_count, error
        nonlocal host_minimum_available, host_maximum_swap
        while not stop.is_set():
            try:
                current = parse_stats(read_stats())
                if set(current) != set(SERVICES):
                    raise ValueError(f"Expected {SERVICES}; observed {tuple(current)}")
                if host_baseline is not None:
                    host = parse_host_memory(read_host_memory())
                    if host["total_mib"] != host_baseline["total_mib"]:
                        raise ValueError("Linux host memory size changed during sampling")
                    host_minimum_available = min(host_minimum_available, host["available_mib"])
                    host_maximum_swap = max(host_maximum_swap, host["swap_used_mib"])
                sample_count += 1
                for service, mib in current.items():
                    peaks[service] = max(peaks.get(service, 0), mib)
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                error = exc
                return
            stop.wait(interval)

    observer = threading.Thread(target=observe, daemon=True)
    observer.start()
    try:
        result = subprocess.run(command, check=False)
    finally:
        stop.set()
        observer.join(timeout=10)
    if error or observer.is_alive() or not sample_count:
        print(
            f"Preview memory sampling incomplete: {error or 'no complete samples'}", file=sys.stderr
        )
        return result.returncode or 1
    print(f"Preview memory samples: {sample_count} (up to every {interval:g}s).")
    for service in SERVICES:
        print(f"Sampled {service} high: {peaks[service]:.1f} MiB")
    print(f"Sum of individual sampled highs: {sum(peaks.values()):.1f} MiB")
    if host_baseline is None:
        print("Sampling excludes the OS, Docker daemon and short peaks between samples.")
    else:
        print("Container figures exclude the OS and Docker daemon.")
        print(f"Linux host usable RAM: {host_baseline['total_mib']:.1f} MiB")
        print(f"Linux host minimum estimated available RAM: {host_minimum_available:.1f} MiB")
        print(f"Linux host initial swap used: {host_baseline['swap_used_mib']:.1f} MiB")
        print(f"Linux host sampled swap-used high: {host_maximum_swap:.1f} MiB")
        print("Host figures include all work on this Linux host; they miss peaks between samples.")
        print("CI-host observations do not establish fitness of the proposed GCP VM.")
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-host", action="store_true", help="Require Linux host measurements"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    raise SystemExit(sample(command, include_host=args.include_host))


if __name__ == "__main__":
    main()
