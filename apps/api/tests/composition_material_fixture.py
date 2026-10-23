"""Disposable test bytes only; not mounted-volume attestation or a secret provider.

Caller supplies freshly generated test PKI/assertion key and fictional DB config.
No environment, normal app settings, profile, production key or Snowflake I/O.
"""

import importlib.util
import sys
from pathlib import Path

from composition_inventory_fixture import implementation as inv
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from test_source_cases import build_test_sources

from ciq_api.source_alpha import SOURCE_TENANTS

_path = Path(__file__).resolve().parents[3] / "scripts/composition_material.py"
_spec = importlib.util.spec_from_file_location("ciq_composition_material_test", _path)
material = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = material
_spec.loader.exec_module(material)

TLS_NAMES = {
    "membership": "membership",
    "broker": "broker",
    "controller": "controller",
    "validator-0": "validator",
    "validator-1": "validator1",
    "reader-0-nonclinical": "reader",
    "reader-0-clinical": "reader_medical",
    "reader-1-nonclinical": "reader1",
    "reader-1-clinical": "reader1_medical",
}


def public(key):
    return key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def bundles(plan, pki, assertion_key, *, local_secret, db_config, db_ca):
    """Create in-memory role maps; caller must explicitly stage each in private tmp.

    The plan's pins must already match the supplied disposable certificates.
    Semantic source data comes only from the closed synthetic test generator.
    Database configuration is an injected disposable fixture, not a live login.
    """
    if (
        type(plan) is not inv.Inventory
        or type(local_secret) is not str
        or len(local_secret) < 32
        or type(db_config) is not dict
        or type(db_ca) is not bytes
        or not db_ca
    ):
        raise material.MaterialDenied()
    identities = {}
    for role, name in TLS_NAMES.items():
        cert_path, key_path, _ = pki[1][name]
        cert_bytes, key_bytes = cert_path.read_bytes(), key_path.read_bytes()
        certificate = x509.load_pem_x509_certificate(cert_bytes)
        key = serialization.load_pem_private_key(key_bytes, password=None)
        if certificate.fingerprint(hashes.SHA256()).hex() != dict(plan.pins)[role] or public(
            certificate.public_key()
        ) != public(key.public_key()):
            raise material.MaterialDenied()
        identities[role] = cert_bytes, key_bytes
    # No CA key is copied. The assertion private key belongs only to broker.
    signer = assertion_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    verify = assertion_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _, _, _, records, details = build_test_sources()
    result = {}
    for role in inv.ROLES:
        certificate, key = identities[role]
        data = {
            "config.json": inv.canonical(plan.config(role)),
            "ca.pem": pki[0].read_bytes(),
            "identity.pem": certificate,
            "identity.key": key,
        }
        if role == "broker":
            data.update(
                {"signer.pem": signer, "local-auth.json": inv.canonical({"secret": local_secret})}
            )
        elif role == "membership":
            data.update({"db.json": inv.canonical(db_config), "db-ca.pem": db_ca})
        else:
            data["verify.pem"] = verify
            if role.startswith("validator-"):
                tenant = SOURCE_TENANTS[int(role[-1])]
                data["source.json"] = inv.canonical(
                    {
                        case.request_id: {
                            "case": case.model_dump(mode="json"),
                            "decisions": details[case.request_id]["decision"],
                            "evidence": details[case.request_id]["evidence"],
                        }
                        for case in records[tenant.tenant_id]
                    }
                )
        result[role] = material.Material.expected(role, plan.fingerprint(role), data), data
    return result
