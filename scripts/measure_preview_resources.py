"""Sample preview container memory while a CI command runs; no local startup."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
from collections.abc import Callable

PREFIX = "cashlessiq-owner-preview-"
SERVICES = ("db", "api", "web", "gateway")
MEMORY = re.compile(r"^(\d+(?:\.\d+)?)(B|KiB|MiB|GiB|TiB)\b")
SCALE = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "TiB": 1024**2}


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

    stop = threading.Event()
    peaks: dict[str, float] = {}
    sample_count = 0
    error: Exception | None = None

    def observe() -> None:
        nonlocal sample_count, error
        while not stop.is_set():
            try:
                current = parse_stats(read_stats())
                if set(current) != set(SERVICES):
                    raise ValueError(f"Expected {SERVICES}; observed {tuple(current)}")
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
    print("Sampling excludes the OS, Docker daemon and short peaks between samples.")
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    raise SystemExit(sample(command))


if __name__ == "__main__":
    main()
