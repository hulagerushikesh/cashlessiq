"""Network-free disposable Linux clock-domain probe, NEVER a health provider.

The fabricated health attestation is test-only; successful execution says
nothing about NTP synchronization, suspend safety or production tolerances.
"""

import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

from ciq_api.worker_clock import (
    SECOND,
    ClockDenied,
    ClockHealth,
    ClockLimits,
    ClockSample,
    SqliteClockGuard,
)

PATH = Path("/state/clock.sqlite")


def sample():
    return ClockSample(
        time.time_ns(),
        time.monotonic_ns(),
        Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    )


def main():
    operation = sys.argv[1]
    if operation == "initialize":
        PATH.parent.chmod(0o700)
        SqliteClockGuard.initialize_for_offline_test(
            PATH, authority="test-authority", generation="test-generation", initial=sample()
        )
        os.chown(PATH, 10001, 10001)
        os.chown(PATH.parent, 10001, 10001)
        print("Explicit disposable state initialized")
        return
    assert os.getuid() == 10001
    latest = {}

    def read_sample():
        value = sample()
        if operation == "latch":
            value = replace(value, wall_ns=value.wall_ns - 3600 * SECOND)
        latest["value"] = value
        return value

    guard = SqliteClockGuard(
        PATH,
        authority="test-authority",
        generation="test-generation",
        sample=read_sample,
        health=lambda: ClockHealth(True, 0, latest["value"].monotonic_ns),
        limits=ClockLimits(100, SECOND, 2 * SECOND, 120 * SECOND),
    )
    if operation in {"latch", "deny"}:
        try:
            guard.check()
        except ClockDenied:
            print("Guard denied as required")
            return
        raise AssertionError("Unsafe state accepted")
    now = guard.check()
    if operation in {"consume", "replay"}:
        try:
            guard.consume("test-authority", "fixed-test-nonce", now + 60, now)
        except ClockDenied:
            assert operation == "replay"
        else:
            assert operation == "consume"
    else:
        assert operation == "observe"
    value = latest["value"]
    print(json.dumps(dict(wall_ns=value.wall_ns, mono_ns=value.monotonic_ns, boot=value.boot_id)))


if __name__ == "__main__":
    main()
