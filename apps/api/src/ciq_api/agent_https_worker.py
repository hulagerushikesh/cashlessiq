"""Inactive private-pipe child. Never selected by an application service.

This module has network capability, but no credential discovery, runtime grant
or live identity. Its same-UID launcher is not production credential isolation.
"""

import os
import resource
import sys

from ciq_api.agent_https_process import MAX_CONTROL_BYTES, run_worker


def main():
    try:
        if not (sys.flags.isolated and sys.dont_write_bytecode and len(sys.argv) == 1):
            return 1
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # No environment/profile/CA override is accepted even on direct manual
        # invocation. The installed interpreter and OS trust store remain trusted.
        # macOS injects its text-encoding hint even with Popen's exact env.
        allowed = {"LANG", "LC_CTYPE"}
        if sys.platform == "darwin":
            allowed.add("__CF_USER_TEXT_ENCODING")
        if set(os.environ) - allowed:
            return 1
        raw = sys.stdin.buffer.read(MAX_CONTROL_BYTES + 1)
        response = run_worker(raw)
        view = memoryview(response)
        while view:
            written = os.write(1, view)
            if written <= 0:
                return 1
            view = view[written:]
        return 0
    except Exception:
        # No tracebacks, protocol values, credential or server diagnostics.
        return 1


if __name__ == "__main__":
    # Avoid buffered private stdout being retried during interpreter shutdown.
    os._exit(main())
