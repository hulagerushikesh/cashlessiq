"""Fake daemon metadata + real private staging/journals, not mounted Linux proof."""

import json
import socket
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.composition_database import DatabaseStaging
from scripts.composition_database_bootstrap_helpers import DatabaseBootstrapHelpers
from scripts.composition_database_cluster_helpers import DatabaseClusterHelpers
from scripts.composition_database_data_helpers import DatabaseDataHelpers
from scripts.composition_database_helpers import DatabaseHelpers, fingerprint
from scripts.composition_database_volume import DatabaseVolume
from scripts.composition_engine import Engine as BoundedEngine
from scripts.composition_helpers import Helpers, HelpersDenied
from scripts.composition_inventory import EDGES, LABEL, ROLES, Inventory, Network
from scripts.composition_journal import Journal, fold
from scripts.composition_material import Material
from scripts.composition_state_helpers import StateHelpers
from scripts.composition_volume import parse


def setup(
    tmp_path,
    role="broker",
    fault=None,
    headroom=lambda: True,
    *,
    state=False,
    database=False,
    provisioned=None,
    database_data=False,
    database_cluster=False,
    database_bootstrap=False,
):
    plan = Inventory(
        "ciq-comp-abcdef123456",
        tuple(
            (kind, "sha256:" + f"{i:064x}")
            for i, kind in enumerate(("worker", "membership", "broker"), 1)
        ),
        tuple((r, f"{i:064x}") for i, r in enumerate((*ROLES, "controller"), 10)),
        tuple(Network(edge, f"{i:064x}", f"10.81.{i}.0/29") for i, edge in enumerate(EDGES, 1)),
    )
    for name in ("resources", "helpers", "staging"):
        (tmp_path / name).mkdir(mode=0o700)
    if provisioned is not None:
        plan, resources = provisioned
    else:
        resources = Journal(tmp_path / "resources", plan.prefix)
    journal = Journal(tmp_path / "helpers", plan.prefix)
    database_cluster = database_cluster or database_bootstrap
    database = database or database_data or database_cluster
    kind = "data" if database_data else "state" if state else "material"
    first = "prepare" if database_data else "initialize" if state or database_cluster else "install"
    if database_bootstrap:
        first = "bootstrap"
    volume = plan.database_volume(kind) if database else plan.volume(role, kind)
    if database:
        role = "database"
    for action in () if provisioned is not None else ("reserve", "observe"):
        resources.record(
            action,
            kind="volume",
            name=volume,
            identity=volume if action == "observe" else None,
            fingerprint="e" * 64,
        )
    if database_cluster and provisioned is None:
        for action in ("reserve", "observe"):
            data_volume = plan.database_volume("data")
            resources.record(
                action,
                kind="volume",
                name=data_volume,
                identity=data_volume if action == "observe" else None,
                fingerprint="d" * 64,
            )
    material = DatabaseStaging if database else Material
    contents = {name: ("synthetic-private-" + name).encode() for name in material.names(role)}
    binding = fingerprint(plan) if database else plan.fingerprint(role)
    staged = (
        None
        if database_data
        else material.expected(role, binding, contents).provision(tmp_path / "staging", contents)
    )

    class Engine:
        fenced = False

        def __init__(self):
            self.calls, self.rows, self.permitted = [], {}, set()

        def permit_incarnation(self, cid):
            self.permitted.add(cid)

        def __call__(self, *args):
            self.calls.append(args)
            assert len([e for e in journal.events if e.get("action") == "reserve"]) == 2
            if args[:2] == ("image", "inspect"):
                return json.dumps(
                    [
                        dict(
                            Id=helper.image,
                            Config=dict(
                                Entrypoint=helper.entrypoint,
                                Cmd=[],
                                User=helper.probe_user,
                                Env=["PYTHONUNBUFFERED=1"],
                            ),
                        )
                    ]
                )
            if args[:2] == ("volume", "inspect"):
                return json.dumps(
                    [
                        dict(
                            Name=args[-1],
                            Driver="local",
                            Scope="local",
                            Options={},
                            Labels={
                                LABEL: plan.prefix,
                                f"{LABEL}.role": role,
                                f"{LABEL}.kind": "data" if args[-1].endswith("-db-data") else kind,
                            },
                        )
                    ]
                )
            if args[:2] == ("container", "ls"):
                return helper.name("verify") if fault == "collision" else ""
            if args[0] == "create":
                mode = args[-1]
                assert args == helper.create(mode)
                cid = ("a" if mode == first else "b") * 64
                self.rows[cid] = container(helper, mode, cid)
                if fault == "unknown-create":
                    raise TimeoutError("private daemon error")
                return cid
            assert args[0] == "inspect" and args[-1] in self.permitted
            row = deepcopy(self.rows[args[-1]])
            if fault in CHANGES:
                CHANGES[fault](row)
            if fault in LATE_CHANGES and row["Config"]["Cmd"] == ["verify"]:
                LATE_CHANGES[fault](row)
            if state and fault == "verify-readonly" and row["Config"]["Cmd"] == ["verify"]:
                row["Mounts"][0]["RW"] = False
            return json.dumps([row])

        def execute(self, *args, private_input):
            self.calls.append(args)
            cid = args[-1]
            assert args == ("start", "--attach", "--interactive", cid) and cid in self.permitted
            mode = self.rows[cid]["Config"]["Cmd"][0]
            if database_data:
                assert json.loads(private_input) == dict(
                    version=1, role=role, fingerprint=helper.material_fingerprint()
                )
            elif state:
                assert json.loads(private_input) == dict(
                    version=1, role=role, generation=plan.generation
                )
            else:
                spec, archive = parse(
                    private_input,
                    install=mode == "install",
                    material_type=DatabaseVolume if database else Material,
                )
                assert spec.records == staged.expected.records
                assert spec.fingerprint == staged.expected.fingerprint
                assert (archive is not None) == (mode == "install")
            self.rows[cid]["State"].update(Status="exited", ExitCode=0)
            if fault == "nonzero":
                self.rows[cid]["State"]["ExitCode"] = 1
            elif fault == "running":
                self.rows[cid]["State"].update(Running=True, Pid=99)
            elif fault == "unknown-start":
                raise TimeoutError("private input not reported")
            result = helper.receipt(mode)
            if fault == "receipt":
                result["role"] = "other"
            if state and fault == "generation":
                result["generation"] = "wrong-generation"
            if fault == "duplicate-json":
                return '{"state":"VERIFIED","state":"VERIFIED"}'
            return json.dumps(result)

    engine = Engine()
    helper_type = (
        DatabaseBootstrapHelpers
        if database_bootstrap
        else DatabaseClusterHelpers
        if database_cluster
        else DatabaseDataHelpers
        if database_data
        else DatabaseHelpers
        if database
        else StateHelpers
        if state
        else Helpers
    )
    helper = helper_type(
        plan,
        *(([]) if database_data else [role if state else staged]),
        image="sha256:" + "c" * 64,
        journal=journal,
        resources=resources,
        engine=engine,
        headroom=headroom,
    )
    return helper, engine, journal, resources


def container(helper, mode, cid):
    return dict(
        Id=cid,
        Name="/" + helper.name(mode),
        Image=helper.image,
        RestartCount=0,
        Config=dict(
            Labels={
                LABEL: helper.plan.prefix,
                f"{LABEL}.helper": mode,
                f"{LABEL}.role": helper.role,
                f"{LABEL}.fingerprint": helper.fingerprint(mode),
            },
            User=helper.user(mode),
            Entrypoint=helper.entrypoint,
            Cmd=[mode],
            Env=["PYTHONUNBUFFERED=1"],
            OpenStdin=True,
            Tty=False,
        ),
        HostConfig=dict(
            ReadonlyRootfs=True,
            Privileged=False,
            CapDrop=["ALL"],
            CapAdd=helper.capabilities(mode),
            SecurityOpt=["no-new-privileges"],
            Memory=128 * 1024**2,
            NanoCpus=500_000_000,
            PidsLimit=32,
            NetworkMode="none",
            RestartPolicy=dict(Name="no", MaximumRetryCount=0),
            IpcMode="private",
        ),
        Mounts=[
            dict(
                Type="volume",
                Name=name,
                Destination=destination,
                RW=writable,
            )
            for name, destination, writable in helper.mounts(mode)
        ],
        NetworkSettings=dict(Networks={"none": dict(IPAddress="", GlobalIPv6Address="")}),
        State=dict(Status="created", Running=False, Pid=0, ExitCode=0),
    )


CHANGES = {
    "image": lambda r: r.update(Image="sha256:" + "f" * 64),
    "identity": lambda r: r.update(Id="f" * 64),
    "labels": lambda r: r["Config"].update(Labels={}),
    "user": lambda r: r["Config"].update(User="123:123"),
    "entrypoint": lambda r: r["Config"].update(Entrypoint=["sh"]),
    "environment": lambda r: r["Config"].update(Env=["UNAPPROVED=1"]),
    "privileged": lambda r: r["HostConfig"].update(Privileged=True),
    "capabilities": lambda r: r["HostConfig"].update(CapAdd=["SYS_ADMIN"]),
    "host-bind": lambda r: r["HostConfig"].update(Binds=["/private:/private"]),
    "network": lambda r: r["HostConfig"].update(NetworkMode="bridge"),
    "port": lambda r: r["HostConfig"].update(PortBindings={"80/tcp": [{}]}),
    "mount": lambda r: r["Mounts"][0].update(Name="foreign"),
    "readonly": lambda r: r["Mounts"][0].update(RW=False),
    "tmpfs": lambda r: r["HostConfig"].update(Tmpfs={"/material": "rw"}),
    "pid": lambda r: r["State"].update(Pid=42),
    "oom": lambda r: r["State"].update(OOMKilled=True),
    "restart": lambda r: r.update(RestartCount=1),
    "auto-remove": lambda r: r["HostConfig"].update(AutoRemove=True),
}

LATE_CHANGES = {
    "verify-writable": lambda r: r["Mounts"][0].update(RW=True),
    "verify-root": lambda r: r["Config"].update(User="0:0"),
    "verify-capability": lambda r: r["HostConfig"].update(CapAdd=["CHOWN"]),
    "verify-extra-mount": lambda r: r["Mounts"].append(dict(Type="bind", Destination="/private")),
}


@pytest.mark.parametrize("role", ROLES)
def test_each_role_requires_separate_install_and_nonroot_readback(tmp_path, role):
    helper, engine, journal, resources = setup(tmp_path, role)
    try:
        assert helper.run() is True
        _, rows, fenced = fold(journal.events)
        assert not fenced and len(rows) == 2 and all(r[2] == "STOPPED" for r in rows.values())
        assert len([a for a in engine.calls if a[0] == "start"]) == 2
        with pytest.raises(HelpersDenied):
            helper.run()
        assert len([a for a in engine.calls if a[0] == "start"]) == 2
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize(
    ("capabilities", "accepted"),
    [
        (["CHOWN"], True),
        (["CAP_CHOWN"], True),
        (["CHOWN", "CAP_CHOWN"], False),
        (["CAP_CHOWN", "CAP_SYS_ADMIN"], False),
        (["cap_chown"], False),
        ("CAP_CHOWN", False),
    ],
)
def test_engine_chown_spelling_without_extra_capabilities(
    tmp_path, monkeypatch, capabilities, accepted
):
    original = container

    def observed(helper, mode, cid):
        row = original(helper, mode, cid)
        if mode == "install":
            row["HostConfig"]["CapAdd"] = capabilities
        return row

    monkeypatch.setattr(sys.modules[__name__], "container", observed)
    helper, engine, journal, resources = setup(tmp_path)
    try:
        if accepted:
            assert helper.run() is True
        else:
            with pytest.raises(HelpersDenied):
                helper.run()
            assert not any(call[0] == "start" for call in engine.calls)
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize(
    "fault",
    [
        *CHANGES,
        "collision",
        "unknown-create",
        "unknown-start",
        "nonzero",
        "running",
        "receipt",
        "duplicate-json",
    ],
)
def test_uncertainty_fences_without_retry_removal_or_false_readback(tmp_path, fault, capsys):
    helper, engine, journal, resources = setup(tmp_path, fault=fault)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        _, rows, fenced = fold(journal.events)
        assert fenced and engine.fenced and len(rows) == 2
        assert any(row[2] != "STOPPED" for row in rows.values())
        assert not any(a[0] in {"rm", "exec", "run"} for a in engine.calls)
        assert len([a for a in engine.calls if a[0] == "start"]) <= 1
        if fault in CHANGES or fault in {"collision", "unknown-create"}:
            assert not any(a[0] == "start" for a in engine.calls)
        assert capsys.readouterr() == ("", "")
    finally:
        journal.close()
        resources.close()


def test_headroom_failure_does_no_engine_work(tmp_path):
    helper, engine, journal, resources = setup(tmp_path, headroom=lambda: False)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        assert not engine.calls and fold(journal.events)[2]
    finally:
        journal.close()
        resources.close()


def containment_engine(helper, engine, *, lost_stop=False, keep_running=False, missing=None):
    """Closed fake stop path; no actual Docker process or resources."""

    class Containment:
        fenced = True

        def __call__(self, *args):
            if args[0] == "stop":
                engine.calls.append(args)
                assert args == ("stop", "--time", "1", args[-1])
                assert args[-1] in helper.owned.values()
                if not keep_running:
                    engine.rows[args[-1]]["State"].update(
                        Status="exited",
                        Running=False,
                        Paused=False,
                        Restarting=False,
                        Pid=0,
                        ExitCode=137,
                    )
                if lost_stop:
                    raise TimeoutError("private stop acknowledgement")
                return args[-1]
            if args == ("inspect", missing):
                engine.calls.append(args)
                raise TimeoutError("private inspection error")
            return engine(*args)

    helper.engine = Containment()


@pytest.mark.parametrize("active", ["Running", "Paused", "Restarting"])
@pytest.mark.parametrize("lost_stop", [False, True])
def test_containment_requires_fresh_exit_not_stop_acknowledgement(tmp_path, active, lost_stop):
    helper, engine, journal, resources = setup(tmp_path)
    try:
        assert helper.run()
        for row in engine.rows.values():
            row["State"].update(Status="running", Running=True, Pid=99)
            row["State"][active] = True
        containment_engine(helper, engine, lost_stop=lost_stop)
        before = deepcopy(resources.events)
        assert helper.contain() is True
        assert resources.events == before and fold(journal.events)[2]
        assert len([a for a in engine.calls if a[0] == "stop"]) == 2
        assert all(r[2] == "STOPPED" for r in fold(journal.events)[1].values())
        assert helper.contain() is True
        assert len([a for a in engine.calls if a[0] == "stop"]) == 2
        with pytest.raises(HelpersDenied):
            helper.run()
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("fault", ["unknown-create", "unknown-start", "nonzero", "receipt"])
def test_failed_run_containment_never_adopts_unknown_create_or_claims_verified(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path, fault=fault)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        containment_engine(helper, engine)
        assert helper.contain() is False  # Verifier was never created.
        rows = fold(journal.events)[1]
        assert rows[("container", helper.name("verify"))][2] == "UNKNOWN"
        assert rows[("container", helper.name("install"))][2] == (
            "UNKNOWN" if fault == "unknown-create" else "STOPPED"
        )
        assert not any(a[0] in {"rm", "run", "exec", "stop"} for a in engine.calls)
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("fault", ["labels", "identity", "image", "mount", "privileged", "network"])
def test_containment_does_not_stop_mismatched_container(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path)
    try:
        assert helper.run()
        cid = helper.owned["install"]
        engine.rows[cid]["State"].update(Running=True, Pid=99, Status="running")
        CHANGES[fault](engine.rows[cid])
        containment_engine(helper, engine)
        assert helper.contain() is False
        assert not any(a[0] == "stop" for a in engine.calls)
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("failure", ["still-running", "missing", "journal"])
def test_containment_uncertainty_returns_false_but_continues_other_owned_helper(tmp_path, failure):
    helper, engine, journal, resources = setup(tmp_path)
    try:
        assert helper.run()
        for row in engine.rows.values():
            row["State"].update(Status="running", Running=True, Pid=99)
        containment_engine(
            helper,
            engine,
            keep_running=failure == "still-running",
            missing=helper.owned["install"] if failure == "missing" else None,
        )
        if failure == "journal":
            journal.failed = True
        assert helper.contain() is False
        stops = [a[-1] for a in engine.calls if a[0] == "stop"]
        assert helper.owned["verify"] in stops
        assert len(stops) == (1 if failure == "missing" else 2)
        assert not any(a[0] in {"rm", "exec", "run"} for a in engine.calls)
    finally:
        journal.close()
        resources.close()


def test_containment_before_attempt_is_denied_without_engine_io(tmp_path):
    helper, engine, journal, resources = setup(tmp_path)
    try:
        with pytest.raises(HelpersDenied):
            helper.contain()
        assert not engine.calls
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("fault", LATE_CHANGES)
def test_installer_success_never_substitutes_for_safe_readonly_verifier(tmp_path, fault):
    helper, engine, journal, resources = setup(tmp_path, fault=fault)
    try:
        with pytest.raises(HelpersDenied):
            helper.run()
        _, rows, fenced = fold(journal.events)
        assert fenced and engine.fenced
        assert rows[("container", helper.name("install"))][2] == "STOPPED"
        assert rows[("container", helper.name("verify"))][2] == "UNKNOWN"
        assert len([a for a in engine.calls if a[0] == "start"]) == 1
    finally:
        journal.close()
        resources.close()


def test_headroom_rechecked_before_second_helper(tmp_path):
    checks = iter([True, True, False])
    helper, engine, journal, resources = setup(tmp_path, headroom=lambda: next(checks))
    try:
        before = deepcopy(resources.events)
        with pytest.raises(HelpersDenied):
            helper.run()
        assert resources.events == before
        assert len([a for a in engine.calls if a[0] == "create"]) == 1
        assert len([a for a in engine.calls if a[0] == "start"]) == 1
        assert fold(journal.events)[2]
    finally:
        journal.close()
        resources.close()


@pytest.mark.parametrize("failed_exit", [False, True])
@pytest.mark.parametrize("kind", ["material", "state", "database"])
def test_coordinator_through_real_bounded_transport_and_fake_cli(tmp_path, failed_exit, kind):
    state = kind == "state"
    helper, _, journal, resources = setup(tmp_path, state=state, database=kind == "database")
    config = tmp_path / "empty-config"
    config.mkdir(mode=0o700)
    metadata = tmp_path / "fake-daemon-public-metadata.json"
    rows = {
        "a" * 64: container(helper, helper.modes[0], "a" * 64),
        "b" * 64: container(helper, "verify", "b" * 64),
    }
    # Fake daemon retains public container metadata only, never helper input.
    metadata.write_text(json.dumps(rows))
    binary = tmp_path / "fake-docker"
    image_row = dict(
        Id=helper.image,
        Config=dict(
            Entrypoint=helper.entrypoint,
            Cmd=[],
            User=helper.probe_user,
            Env=["PYTHONUNBUFFERED=1"],
        ),
    )
    volume_row = dict(
        Name=helper.volume_name(),
        Driver="local",
        Scope="local",
        Options={},
        Labels={
            LABEL: helper.plan.prefix,
            f"{LABEL}.role": helper.role,
            f"{LABEL}.kind": helper.kind,
        },
    )
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json,sys\n"
        f"path={str(metadata)!r}\n"
        "with open(path) as f: rows=json.load(f)\n"
        "args=sys.argv[5:]\n"
        "if args[:2]==['image','inspect']:\n"
        f" print({json.dumps([image_row])!r})\n"
        "elif args[:2]==['volume','inspect']:\n"
        f" print({json.dumps([volume_row])!r})\n"
        "elif args[:2]==['container','ls']: print('')\n"
        f"elif args[0]=='create': print(('a' if args[-1]=={helper.modes[0]!r} else 'b')*64)\n"
        "elif args[0]=='inspect': print(json.dumps([rows[args[-1]]]))\n"
        "elif args[:3]==['start','--attach','--interactive']:\n"
        " cid=args[-1]; mode=rows[cid]['Config']['Cmd'][0]\n"
        " body=json.loads(sys.stdin.buffer.read())\n"
        f" assert ('archive' in body)==(mode=='install' and not {state!r})\n"
        f" assert body[{('generation' if state else 'fingerprint')!r}]=="
        f"{(helper.plan.generation if state else helper.material_fingerprint())!r}\n"
        f" rows[cid]['State'].update(Status='exited',ExitCode={1 if failed_exit else 0})\n"
        " with open(path,'w') as f: json.dump(rows,f)\n"
        f" print(json.dumps({dict((m, helper.receipt(m)) for m in helper.modes)!r}[mode]))\n"
        "else: sys.exit(2)\n"
    )
    binary.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix="ciq-helper-", dir="/tmp") as short:
        endpoint = str(Path(short) / "engine.sock")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(endpoint)
        try:
            helper.engine = BoundedEngine(
                binary=str(binary),
                socket=endpoint,
                config=config,
                commands=helper.commands(),
                deadline_ns=time.monotonic_ns() + 30_000_000_000,
            )
            if failed_exit:
                with pytest.raises(HelpersDenied):
                    helper.run()
                assert helper.engine.fenced and fold(journal.events)[2]
            else:
                assert helper.run() is True
                assert len(helper.engine.incarnations) == 2
                assert all(r[2] == "STOPPED" for r in fold(journal.events)[1].values())
            assert "synthetic-private" not in metadata.read_text()
            assert "synthetic-private" not in (journal.root / "events.jsonl").read_text()
        finally:
            listener.close()
            journal.close()
            resources.close()
