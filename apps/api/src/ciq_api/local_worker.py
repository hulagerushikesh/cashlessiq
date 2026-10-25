"""Small local preview worker; the same leases support a separate worker later."""

import logging
from threading import Event, Thread

from ciq_api.jobs import run_once


def start_local_worker(engine):
    stop = Event()

    def work():
        while not stop.is_set():
            try:
                busy = run_once(engine)
            except Exception:
                # No document, SQL parameters or raw driver diagnostics in logs.
                logging.getLogger(__name__).warning("Local job iteration unavailable")
                busy = False
            if not busy:
                stop.wait(1)

    thread = Thread(target=work, name="ciq-local-jobs", daemon=True)
    thread.start()
    return stop, thread
