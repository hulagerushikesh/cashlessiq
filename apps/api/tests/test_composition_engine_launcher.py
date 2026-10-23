"""Real actor/CLI processes + fake Docker transcript + actual retained journal.

No daemon connection, real container, resource deletion or operational activation.
"""

import importlib
import json
import socket
import sys
import tempfile
import time
from pathlib import Path

import pytest
from composition_journal_fixture import implementation as ledger
from composition_launcher import Launcher
from test_composition_launcher_journal import recovery, setup

transport = importlib.import_module(ledger.__package__ + ".composition_engine")


@pytest.mark.parametrize("blocked", [False, True])
def test_launcher_journal_with_bounded_process_transport(tmp_path, blocked):
    # Capture a closed trusted transcript using existing complete fake metadata.
    (tmp_path / "reference").mkdir(mode=0o700)
    reference, fake, old_journal = setup(tmp_path / "reference")
    transcript = []

    def record(*args):
        output = fake(*args)
        transcript.append([args, output])
        return output

    reference.engine = record
    reference(reference.services[0], fake.binding)
    assert not reference.cleanup(1_000_000_000)  # Seven unlaunched intentions stay unknown.
    old_journal.close()

    parent = tmp_path / "journal"
    parent.mkdir(mode=0o700)
    journal = ledger.Journal(parent, reference.plan.prefix)
    config = tmp_path / "config"
    config.mkdir(mode=0o700)
    transcript_file, cursor = tmp_path / "transcript.json", tmp_path / "cursor"
    transcript_file.write_text(json.dumps(transcript))
    cursor.write_text("0")
    executable = tmp_path / "fake-docker"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json,sys,time\nfrom pathlib import Path\n"
        f"rows=json.loads(Path({str(transcript_file)!r}).read_text())\n"
        f"cursor=Path({str(cursor)!r})\n"
        "i=int(cursor.read_text()); args=sys.argv[5:]\n"
        "assert rows[i][0]==args\n"
        "cursor.write_text(str(i+1))\n"
        f"if {blocked!r} and args[0]=='create': time.sleep(30)\n"
        "sys.stdout.write(rows[i][1])\n"
    )
    executable.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix="ciq-engine-", dir="/tmp") as short:
        endpoint = str(Path(short) / "engine.sock")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(endpoint)
        try:
            engine = transport.Engine(
                binary=str(executable),
                socket=endpoint,
                config=config,
                commands=tuple(
                    (*row[0][:-1], "{incarnation}")
                    if len(row[0][-1]) == 64
                    and (
                        row[0][0] in {"inspect", "start", "stop"}
                        or row[0][:2] == ("network", "connect")
                    )
                    else tuple(row[0])
                    for row in transcript
                ),
                deadline_ns=time.monotonic_ns() + 60_000_000_000,
                budget_ns=500_000_000 if blocked else 2_000_000_000,
            )
            launcher = Launcher(
                reference.plan,
                engine=engine,
                material_check=lambda *args: True,
                auxiliaries=reference.auxiliaries,
                journal=journal,
            )
            if blocked:
                with pytest.raises(ValueError, match="launch failed"):
                    launcher(launcher.services[0], fake.binding)
                assert engine.fenced and launcher.closed
                result, resources = recovery(journal)
                assert result.fenced
                assert {r[2] for r in resources.values()} == {"UNKNOWN"}
                # A killed CLI is not proof that daemon creation did not occur.
                assert sum(r[1] is not None for r in resources.values()) == 0
                with pytest.raises(ValueError, match="launch denied"):
                    launcher(launcher.services[1], fake.binding)
            else:
                owned = launcher(launcher.services[0], fake.binding)
                assert owned.incarnation == fake.rows[launcher.services[0].role]["Id"]
                assert not launcher.cleanup(1_000_000_000)
                assert int(cursor.read_text()) == len(transcript)
                result, resources = recovery(journal)
                assert result.fenced
                assert sum(r[2] == "STOPPED" for r in resources.values()) == 1
                assert sum(r[2] == "UNKNOWN" for r in resources.values()) == 7
        finally:
            journal.close()
            listener.close()
