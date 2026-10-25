"""Actual per-role test files and canonical preparation, no Docker/database calls."""

import importlib
import io
import json
import tarfile
from dataclasses import replace
from unittest.mock import Mock

import broker_composition_service as broker
import pytest
from composition_inventory_fixture import implementation as inv
from composition_material_fixture import TLS_NAMES, bundles, material
from composition_service_fixture import service as workers
from membership_composition_fixture import service as members
from test_composition_launcher import FakeDocker, Launcher, plan
from test_worker_guard_container_fixture import topology_fixture as topology_fixture
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import pki as pki


@pytest.fixture
def materials(tmp_path, pki, assertion_key):
    p = replace(plan(), pins=tuple((role, pki[1][name][2]) for role, name in TLS_NAMES.items()))
    root = tmp_path / "material"
    root.mkdir(mode=0o700)
    generated = bundles(
        p,
        pki,
        assertion_key,
        local_secret="fictional-test-local-secret-32-characters",
        db_config={"host": "ciq-membership-db.test", "password": "fictional-not-a-login"},
        db_ca=pki[0].read_bytes(),
    )
    staged = {role: spec.provision(root, data) for role, (spec, data) in generated.items()}
    return p, staged


def test_staged_material_replaces_fake_launcher_material_callback(materials):
    p, staged = materials
    engine = FakeDocker(p)

    def check(role, descriptor):
        return descriptor == p.descriptor(role) and staged[role].verify(role, p.fingerprint(role))

    launcher = Launcher(
        p, engine=engine, material_check=check, auxiliaries={"db": "d" * 64, "controller": "e" * 64}
    )
    assert launcher.verify(launcher.services)
    # An extra credential file must deny the full preflight, even if all engine
    # observations remain unchanged. No create/start or repair may follow.
    (staged["reader-0-clinical"].root / "signer.pem").touch(mode=0o400)
    assert not launcher.verify(launcher.services)
    assert not any(call[0] in {"create", "start"} for call in engine.calls)


def test_actual_staged_bundles_pass_private_volume_helper_wire(materials):
    p, staged = materials
    volume = importlib.import_module(inv.__package__ + ".composition_volume")
    for role, bundle in staged.items():
        for install in (False, True):
            frame = volume.request(bundle, install=install)
            spec, archive = volume.parse(frame, install=install)
            assert spec == bundle.expected and spec.fingerprint == p.fingerprint(role)
            assert (archive is not None) is install


def test_all_eight_bundles_match_service_parsers_and_key_boundaries(
    materials,
    topology_fixture,
    tmp_path,
    assertion_key,
    pki,
):
    p, staged = materials
    guards = tmp_path / "guards"
    guards.mkdir()
    private_values = [pki[1][name][1].read_bytes() for name in TLS_NAMES.values()]
    assert len(set(private_values)) == 9
    for role, bundle in staged.items():
        root = bundle.root
        raw = json.loads((root / "config.json").read_text())
        assert raw == p.config(role)
        assert set(x.name for x in root.iterdir()) == material.names(role)
        data = bundle.archive(role, p.fingerprint(role))
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            copied = {r.name: archive.extractfile(r).read() for r in archive if r.isfile()}
        own_key = pki[1][TLS_NAMES[role]][1].read_bytes()
        assert copied["identity.key"] == own_key
        assert not any(
            key in value for key in private_values if key != own_key for value in copied.values()
        )
        if role == "membership":
            members.configuration({k: raw[k] for k in ("listen", "peers")})
            members.broker_configuration(raw["broker"], raw)
            assert b"fictional-not-a-login" in copied["db.json"]
            continue  # No DB factory/connection is created by this test.
        directory = guards / role
        directory.mkdir()
        topology_fixture.initialize(role, directory=directory)
        guard, evidence = topology_fixture.load(directory=directory)
        target = broker if role == "broker" else workers
        handler, context = target.prepare(
            root,
            raw,
            guard=guard,
            evidence=evidence,
            generation=p.generation,
        )
        assert handler is not None and context(True) is not None
        assert not any("db" in name for name in copied)
        if role != "broker":
            from cryptography.hazmat.primitives.serialization import load_pem_public_key

            assert (
                load_pem_public_key(copied["verify.pem"]).public_numbers()
                == assertion_key.public_key().public_numbers()
            )
        if role.startswith("validator-"):
            rows = json.loads(copied["source.json"])
            assert set(rows) == ({"GOL001"} if role.endswith("0") else {"GOL024", "GOL027"})
            if role.endswith("1"):
                assert all(row["decisions"] == [] for row in rows.values())


def test_wrong_pin_denies_before_any_material_is_staged(pki, assertion_key, tmp_path):
    with pytest.raises(material.MaterialDenied):
        bundles(
            plan(),
            pki,
            assertion_key,
            local_secret="x" * 32,
            db_config={},
            db_ca=pki[0].read_bytes(),
        )
    assert list(tmp_path.iterdir()) == []


def test_no_ambient_configuration_or_docker_access(materials, monkeypatch):
    p, staged = materials
    # All dependency preparation above uses explicit fixture bytes. Local checks
    # remain read-only and cannot invoke process/network/environment discovery.
    import subprocess

    execute = Mock(side_effect=AssertionError("Unexpected process"))
    monkeypatch.setattr(subprocess, "run", execute)
    for role in inv.ROLES:
        assert staged[role].verify(role, p.fingerprint(role))
    execute.assert_not_called()
