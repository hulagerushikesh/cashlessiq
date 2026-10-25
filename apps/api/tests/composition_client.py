"""Closed controller-side physical test probe; never a normal product endpoint."""

import json
import os
import signal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from broker_composition_service import PrivateBrokerClient

from ciq_api.worker_transport import PrivateEndpoint, tls_context

MAX_FRAME = 32768


def pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError("Invalid disposable probe")
        result[key] = value
    return result


def summary(frame):
    if type(frame) is not bytes or not 0 < len(frame) <= MAX_FRAME:
        raise ValueError("Invalid disposable probe")
    raw = json.loads(frame, object_pairs_hook=pairs)
    names = {"address", "pin", "ca", "certificate", "private_key", "token", "request_id"}
    if (
        type(raw) is not dict
        or set(raw) != names
        or any(type(value) is not str or not 0 < len(value) <= 8192 for value in raw.values())
    ):
        raise ValueError("Invalid disposable probe")
    endpoint = PrivateEndpoint(raw["address"], 8443)
    with TemporaryDirectory(prefix="ciq-controller-", dir="/tmp") as directory:
        root = Path(directory)
        for field, name in (
            ("ca", "ca.pem"),
            ("certificate", "identity.pem"),
            ("private_key", "identity.key"),
        ):
            path = root / name
            with path.open("xb") as output:
                output.write(raw[field].encode())
            path.chmod(0o400)
        client = PrivateBrokerClient(
            endpoint=endpoint,
            context=tls_context(
                server=False,
                ca=root / "ca.pem",
                certificate=root / "identity.pem",
                private_key=root / "identity.key",
            ),
            server_pin=raw["pin"],
            server_audience="broker",
        )
        result = client.summary(raw["token"], raw["request_id"])
        return {"state": "VERIFIED", "summary": result.model_dump(mode="json")}


def main():
    if os.geteuid() != 10001 or os.getegid() != 10001 or len(sys.argv) != 2:
        return 2
    if sys.argv[1] == "hold":
        stopped = Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stopped.set())
        stopped.wait()
        return 0
    if sys.argv[1] != "summary":
        return 2
    try:
        result = summary(sys.stdin.buffer.read(MAX_FRAME + 1))
    except Exception:
        result = {"state": "DENIED"}  # No credentials, raw requests or driver text.
    print(json.dumps(result, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
