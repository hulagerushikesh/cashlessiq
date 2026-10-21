"""Inactive bounded collector prototype. REQUIRED injected fake launcher only.

No default subprocess launcher, host clock sampler, key, signing or daemon access.
The fixed candidate request does not pin/attest an installed binary or host policy.
Real executable/version/monitoring transport acceptance remains a separate gate.
"""

import os
import selectors
import signal
import subprocess
import time
from collections.abc import Callable
from contextlib import suppress

from ciq_api.worker_health import (
    CollectionWindow,
    HealthBinding,
    HealthDenied,
    HealthEvidence,
    HealthNow,
    HealthPolicy,
    make_evidence,
    parse_tracking,
)

# Candidate loopback monitoring only: one literal address, no fallback/socket,
# DNS, environment-selected program, interactive command or clock-setting action.
# Offline launchers assert this request and substitute a disposable fake child.
TRACKING_REQUEST = (
    "/usr/bin/chronyc",
    "-n",
    "-c",
    "-h",
    "127.0.0.1",
    "-p",
    "323",
    "tracking",
)
OUTPUT_LIMIT = 2048
MAX_TEST_TIMEOUT_NS = 5_000_000_000
CLEANUP_SECONDS = 0.25


def _receive(process: subprocess.Popen, deadline: int) -> bytes:
    output = bytearray()
    with selectors.DefaultSelector() as selector:
        for pipe in (process.stdout, process.stderr):
            if pipe is None:
                raise ValueError("Missing stream")
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic_ns()
            if remaining <= 0:
                raise ValueError("Collection deadline")
            for key, _ in selector.select(timeout=min(remaining / 1_000_000_000, 0.05)):
                # At most one byte beyond the accepted stdout bound; stderr is
                # never retained or disclosed and any diagnostic denies.
                limit = OUTPUT_LIMIT + 1 - len(output) if key.fileobj is process.stdout else 1
                chunk = os.read(key.fileobj.fileno(), limit)
                if not chunk:
                    selector.unregister(key.fileobj)
                elif key.fileobj is process.stderr:
                    raise ValueError("Unexpected diagnostic")
                else:
                    output.extend(chunk)
                    if len(output) > OUTPUT_LIMIT:
                        raise ValueError("Collection output bound")
        remaining = deadline - time.monotonic_ns()
        if remaining <= 0 or process.wait(timeout=remaining / 1_000_000_000) != 0:
            raise ValueError("Collection unavailable")
    return bytes(output)


def _cleanup(process: subprocess.Popen) -> None:
    # The trusted test launcher must honor start_new_session=True. Kill the
    # dedicated group even if the direct child exited with inherited pipes open.
    # Escaped descendants / OS-blocked spawn or kill need real host containment;
    # this is not a sandbox or a hard real-time process-lifecycle guarantee.
    try:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=CLEANUP_SECONDS)
    finally:
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def collect_for_offline_test(
    *,
    launch: Callable[..., subprocess.Popen],
    sample: Callable[[], HealthNow],
    binding: HealthBinding,
    policy: HealthPolicy,
    sequence: int,
    timeout_ns: int,
) -> HealthEvidence:
    """Collect one fake response, bracket it, and validate before returning a claim.

    There is no retry or fallback. No signature is issued here. An injected
    launcher/sampler is trusted test code, not an application extension point.
    The receive deadline includes time spent in launch, but cannot preempt a
    blocked launcher or sampler; those remain host-acceptance obligations.
    """
    try:
        if (
            not callable(launch)
            or not callable(sample)
            or not isinstance(binding, HealthBinding)
            or not isinstance(policy, HealthPolicy)
            or type(timeout_ns) is not int
            or not 0 < timeout_ns <= MAX_TEST_TIMEOUT_NS
            or type(sequence) is not int
            or not 0 < sequence <= 2**63 - 1
        ):
            raise ValueError("Invalid collection configuration")
        start = sample()
        if not isinstance(start, HealthNow) or start.boot_id != binding.boot_id:
            raise ValueError("Invalid domain")
        deadline = time.monotonic_ns() + min(timeout_ns, policy.max_collection_ns)
        process = launch(
            TRACKING_REQUEST,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            start_new_session=True,
            cwd="/",
            env={"LANG": "C", "LC_ALL": "C"},
        )
        try:
            payload = _receive(process, deadline)
        finally:
            _cleanup(process)
        end = sample()
        if (
            time.monotonic_ns() >= deadline
            or not isinstance(end, HealthNow)
            or end.boot_id != start.boot_id
        ):
            raise ValueError("Invalid domain")
        window = CollectionWindow(
            start_wall_ns=start.wall_ns,
            end_wall_ns=end.wall_ns,
            start_monotonic_ns=start.monotonic_ns,
            end_monotonic_ns=end.monotonic_ns,
            start_boottime_ns=start.boottime_ns,
            end_boottime_ns=end.boottime_ns,
        )
        return make_evidence(
            parse_tracking(payload, policy=policy),
            binding=binding,
            sequence=sequence,
            window=window,
            policy=policy,
        )
    except Exception:
        raise HealthDenied("Health evidence denied") from None
