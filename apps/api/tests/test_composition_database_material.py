"""Prepared DB material through real role staging; no DB connection or Docker."""

import importlib
import json
from dataclasses import replace

from composition_journal_fixture import implementation as ledger
from composition_material_fixture import TLS_NAMES, bundles
from test_composition_launcher import plan
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import pki as pki

database = importlib.import_module(ledger.__package__ + ".composition_database")
db_wire = importlib.import_module(ledger.__package__ + ".composition_database_volume")
db_helpers = importlib.import_module(ledger.__package__ + ".composition_database_helpers")


def test_generated_db_credentials_reach_only_membership_staged_bundle(
    tmp_path,
    pki,
    assertion_key,
):
    p = replace(plan(), pins=tuple((role, pki[1][name][2]) for role, name in TLS_NAMES.items()))
    db = database.prepare(p)
    credential = json.loads(db.membership["db.json"])
    assert credential["query"]["hostaddr"] == p.address("member-db", "db")
    prepared = bundles(
        p,
        pki,
        assertion_key,
        local_secret="fictional-test-local-secret-32-characters",
        db_config=credential,
        db_ca=db.membership["db-ca.pem"],
    )
    root = tmp_path / "material"
    root.mkdir(mode=0o700)
    staged_db = database.DatabaseStaging.expected(
        "database", db_helpers.fingerprint(p), db.server
    ).provision(root, db.server)
    for install in (False, True):
        frame = db_wire.request(staged_db, install=install)
        parsed, archive = db_wire.volume.parse(
            frame, install=install, material_type=db_wire.DatabaseVolume
        )
        assert parsed.fingerprint == db_helpers.fingerprint(p)
        assert (archive is not None) is install
    for role, (spec, data) in prepared.items():
        staged = spec.provision(root, data)
        assert staged.verify(role, p.fingerprint(role))
        if role == "membership":
            assert (staged.root / "db.json").read_bytes() == db.membership["db.json"]
            assert (staged.root / "db-ca.pem").read_bytes() == db.membership["db-ca.pem"]
        else:
            assert "db.json" not in data and "db-ca.pem" not in data
            assert not any(credential["password"].encode() in value for value in data.values())
        assert all(
            private not in value
            for private in (db.server["server.key"], db.server["admin-password"])
            for value in data.values()
        )
        assert "bootstrap.sql" not in data
