"""TEST TARGET ONLY: actual delegated mTLS handlers with synthetic input/membership.

No application login, SQL, Snowflake, live credentials or production listener.
The synthetic membership file is not a database authorization implementation.
"""

import json
import sys
import time
from pathlib import Path
from threading import Thread

import jwt
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_models import SourceCase
from ciq_api.source_scopes import source_alpha_scopes
from ciq_api.validation_worker import OfflineValidationWorker, ValidationInputs
from ciq_api.worker_authority import Membership, WorkerDenied
from ciq_api.worker_delegation import (
    DelegatedSummaryAuthority,
    DetailAuthority,
    OfflineDelegatedValidator,
    OfflineReadRelay,
    issue_detail_assertion,
)
from ciq_api.worker_membership import PrivateMembershipClient, PrivateMembershipServer
from ciq_api.worker_transport import (
    PrivateEndpoint,
    PrivateSummaryClient,
    PrivateSummaryServer,
    tls_context,
)

ROOT = Path("/run/ciq")
TENANT = SOURCE_TENANTS[0].tenant_id
SUBJECT = str(SOURCE_TENANTS[0].profiles[0].user_id)
AUDIENCES = {
    "broker": "broker",
    "reader": "reader:0:nonclinical",
    "validator": "validator:0",
    "membership": "membership:0",
}


def context(server=False):
    return tls_context(
        server=server,
        ca=ROOT / "ca.pem",
        certificate=ROOT / "identity.pem",
        private_key=ROOT / "identity.key",
    )


def transport(config, target, *, membership=False, pin=None, audience=None):
    cls = PrivateMembershipClient if membership else PrivateSummaryClient
    extra = (
        {"tenant_id": TENANT}
        if membership
        else {"operation": "read_detail" if target == "reader" else "validate_summary"}
    )
    return cls(
        endpoint=PrivateEndpoint(config["targets"][target], 8443),
        context=context(),
        server_pin=pin or config["pins"][target],
        server_audience=audience or AUDIENCES[target],
        **extra,
    )


def serve(config, role):
    peers = {
        config["pins"][name]: AUDIENCES[name]
        for name in (
            {"broker"}
            if role == "reader"
            else {"reader"}
            if role == "validator"
            else {"reader", "validator"}
        )
    }
    if role == "membership":

        def lookup(subject, tenant):
            state = json.loads((ROOT / "state.json").read_text())
            return (
                Membership(tenant, state["role"])
                if subject == SUBJECT and state["role"] is not None
                else None
            )

        listeners = [
            PrivateMembershipServer(
                endpoint=PrivateEndpoint(address, 8443),
                context=context(True),
                peers=peers,
                tenants={aud: TENANT for aud in peers.values()},
                lookup=lookup,
            )
            for address in config["listen"]
        ]
    else:
        common = dict(
            public_key=(ROOT / "verify.pem").read_bytes(),
            tenant_id=TENANT,
            scopes=source_alpha_scopes(),
            membership=transport(config, "membership", membership=True).lookup,
            clock=lambda: int(time.time()),
        )
        if role == "reader":
            authority = DetailAuthority(
                **common,
                audience=AUDIENCES[role],
                disclosure="nonclinical",
            )
            relay = OfflineReadRelay(
                authority=authority,
                public_key=common["public_key"],
                validator_audience=AUDIENCES["validator"],
                invoke_validator=transport(config, "validator").summary,
            )

            def callback(token, *, peer):
                assert peer.audience == "broker"
                return relay.summary(token)
        else:
            authority = DelegatedSummaryAuthority(
                **common,
                audience=AUDIENCES[role],
                readers={AUDIENCES["reader"]: "nonclinical"},
            )
            fixture = json.loads((ROOT / "fixture.json").read_text())
            inputs = ValidationInputs(
                SourceCase.model_validate_json(json.dumps(fixture["case"])),
                fixture["decisions"],
                fixture["evidence"],
            )
            worker = OfflineValidationWorker(
                authority=authority,
                scope=source_alpha_scopes().get(TENANT),
                read_inputs=lambda _: inputs,
            )
            callback = OfflineDelegatedValidator(authority, worker).validate
        listeners = [
            PrivateSummaryServer(
                endpoint=PrivateEndpoint(address, 8443),
                context=context(True),
                peers=peers,
                validate=callback,
                operation="read_detail" if role == "reader" else "validate_summary",
            )
            for address in config["listen"]
        ]
    for listener in listeners:
        Thread(target=listener.serve_forever, daemon=True).start()
    Path("/tmp/ready").touch()
    print("READY", flush=True)
    try:
        while True:
            time.sleep(1)
    finally:
        for listener in listeners:
            listener.shutdown()
            listener.server_close()


def check(config, action):
    assert not (ROOT / "identity-ca.key").exists()
    assert (ROOT / "signing.key").exists()  # Only test broker has assertion signer.
    key = (ROOT / "signing.key").read_bytes()

    def issue():
        return issue_detail_assertion(
            key,
            subject=SUBJECT,
            membership=Membership(TENANT, "processor"),
            reader_audience=AUDIENCES["reader"],
            validator_audience=AUDIENCES["validator"],
            request_id="GOL001",
            scopes=source_alpha_scopes(),
            now=int(time.time()),
        )

    client = transport(config, "reader")
    if action == "deny":
        try:
            client.summary(issue())
        except WorkerDenied:
            print("PASS: membership unavailable/revoked denies delivery")
            return
        raise AssertionError("Membership denial bypassed")
    token = issue()
    result = client.summary(token)
    assert result.recommendation.state == "SAVED"
    assert result.recommendation.payable_inr == 95_000
    for field in ('"lines"', '"decision_json"', '"clinical_note"', '"calc"', '"summary"'):
        assert field not in result.model_dump_json()
    for request in (
        lambda: client.summary(token),
        lambda: client.summary("tampered-capability"),
        lambda: transport(config, "reader", pin="0" * 64).summary(issue()),
        lambda: transport(config, "reader", audience="reader:foreign").summary(issue()),
        lambda: transport(config, "validator").summary(issue()),
    ):
        try:
            request()
        except WorkerDenied:
            continue
        raise AssertionError("Negative transport/capability check accepted")
    claims = jwt.decode(issue(), options={"verify_signature": False})
    claims["tenant"] = str(SOURCE_TENANTS[1].tenant_id)
    try:
        client.summary(jwt.encode(claims, key, algorithm="RS256"))
    except WorkerDenied:
        pass
    else:
        raise AssertionError("Cross-tenant capability accepted")
    print("PASS: delegated SAVED summary; replay/tamper/pin/URI/direct-hop/tenant denied")


if __name__ == "__main__":
    action, role = sys.argv[1:]
    config = json.loads((ROOT / "config.json").read_text())
    expected = {"identity.key", "identity.pem", "ca.pem", "verify.pem", "config.json"}
    expected |= (
        {"signing.key"}
        if role == "broker"
        else {"state.json"}
        if role == "membership"
        else {"fixture.json"}
        if role == "validator"
        else set()
    )
    assert {path.name for path in ROOT.iterdir()} == expected
    try:
        (ROOT / "identity.key").open("wb")
    except OSError:
        pass
    else:
        raise AssertionError("Identity mount is writable")
    if action == "serve":
        assert role != "broker" and not (ROOT / "signing.key").exists()
        assert not (ROOT / "state.json").exists() or role == "membership"
        serve(config, role)
    elif action == "self-deny":
        assert role == "reader"
        config["targets"]["reader"] = config["listen"][0]
        try:
            transport(config, "reader").summary("opaque")
        except WorkerDenied:
            print("PASS: reader certificate cannot impersonate broker")
        else:
            raise AssertionError("Wrong client certificate accepted")
    else:
        assert role == "broker"
        check(config, action)
