"""Fresh test identities for the explicit private integration subnets only."""

from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Network

from composition_inventory_fixture import implementation as inv
from composition_material_fixture import TLS_NAMES
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

SUBNETS = dict(
    zip(inv.EDGES, tuple(IPv4Network("172.30.252.0/24").subnets(new_prefix=29))[:18], strict=True)
)


def create(root):
    root.mkdir(mode=0o700)
    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable physical CI CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(issuer)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False), True
        )
        .sign(ca_key, hashes.SHA256())
    )

    def write(name, data):
        path = root / name
        with path.open("xb") as output:
            output.write(data)
        path.chmod(0o400)
        return path

    ca_path = write("ca.pem", ca.public_bytes(serialization.Encoding.PEM))
    identities = {}
    for role, name in TLS_NAMES.items():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        addresses = [
            network.network_address + 2 + inv.EDGES[edge].index(role)
            for edge, network in SUBNETS.items()
            if role in inv.EDGES[edge]
        ]
        assert addresses
        leaf = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, role)]))
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(
                x509.ExtendedKeyUsage(
                    [ExtendedKeyUsageOID.CLIENT_AUTH]
                    if role == "controller"
                    else [ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]
                ),
                True,
            )
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.UniformResourceIdentifier(
                            "urn:cashlessiq:worker:" + inv.AUDIENCES[role]
                        ),
                        *[x509.IPAddress(address) for address in addresses],
                    ]
                ),
                False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        identities[name] = (
            write(name + ".pem", leaf.public_bytes(serialization.Encoding.PEM)),
            write(
                name + ".key",
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            ),
            leaf.fingerprint(hashes.SHA256()).hex(),
        )
    return ca_path, identities
