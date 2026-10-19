"""Synthetic read isolation, role masking, bounded contracts, and no writes."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from ciq_api.auth import issue_local_token
from ciq_api.cases import SyntheticCaseRepository
from ciq_api.main import create_app
from ciq_api.models import Membership, Tenant
from ciq_api.seed import PROFILES, TENANT_ID


def bearer(settings, profile="processor", tenant_id=TENANT_ID):
    return {"Authorization": f"Bearer {issue_local_token(settings, profile, tenant_id)}"}


@pytest.mark.parametrize("path", ["/v1/cases", "/v1/cases/GOL001"])
def test_case_reads_require_auth(client, path):
    assert client.get(path).status_code == 401


def test_queue_filter_search_pagination_and_no_clinical_fields(client, settings):
    headers = bearer(settings)
    response = client.get("/v1/cases?page_size=1", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["items"][0]["request_id"] == "GOL001"
    assert "clinical_note" not in data["items"][0]
    assert "diagnosis" not in data["items"][0]
    assert (
        client.get("/v1/cases?page=2&page_size=1", headers=headers).json()["items"][0]["request_id"]
        == "GOL024"
    )
    query = client.get("/v1/cases?outcome=QUERY&search=gol027", headers=headers).json()
    assert query["total"] == 1
    assert query["items"][0]["payable_inr"] is None
    assert client.get("/v1/cases?search=absent", headers=headers).json()["items"] == []
    assert client.get("/v1/cases?page=4", headers=headers).json()["items"] == []


@pytest.mark.parametrize("profile", ["processor", "medical_officer", "auditor"])
def test_detail_role_masking_and_immutable_snapshot(client, settings, profile):
    response = client.get("/v1/cases/GOL024", headers=bearer(settings, profile))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["clinical_visible"] == (profile == "medical_officer")
    assert bool(data["clinical_note"]) == (profile == "medical_officer")
    assert bool(data["diagnosis"]) == (profile == "medical_officer")
    assert data["outcome"] == "REFER"
    assert data["payable_inr"] is None
    assert data["lines"] == []
    assert data["refer_reasons"]
    assert "NIA-6.1" in {item["clause_id"] for item in data["evidence"]}
    # A masked read must not mutate the repository copy used for the next role.
    medical = client.get("/v1/cases/GOL024", headers=bearer(settings, "medical_officer"))
    assert medical.json()["clinical_note"]


def test_cross_tenant_reads_do_not_leak_even_with_valid_membership(client, settings, engine):
    other = uuid4()
    with Session(engine) as session, session.begin():
        session.add(Tenant(id=other, name="Other synthetic tenant"))
        session.flush()
        session.add(
            Membership(tenant_id=other, user_id=UUID(PROFILES["processor"][0]), role="processor")
        )
    headers = bearer(settings, tenant_id=other) | {"X-Tenant-ID": str(TENANT_ID)}
    assert client.get("/v1/cases", headers=headers).json()["total"] == 0
    assert client.get("/v1/cases/GOL001", headers=headers).status_code == 404
    assert client.get("/v1/cases/UNKNOWN", headers=headers).status_code == 404


def test_case_membership_revocation_is_immediate(client, settings, engine):
    headers = bearer(settings)
    assert client.get("/v1/cases/GOL001", headers=headers).status_code == 200
    with Session(engine) as session, session.begin():
        session.get(Membership, (TENANT_ID, UUID(PROFILES["processor"][0]))).active = False
    assert client.get("/v1/cases", headers=headers).status_code == 403
    assert client.get("/v1/cases/GOL001", headers=headers).status_code == 403


@pytest.mark.parametrize("query", ["outcome=DENY", "page=0", "page_size=51", "search=" + "a" * 81])
def test_invalid_filters_fail_validation(client, settings, query):
    assert client.get(f"/v1/cases?{query}", headers=bearer(settings)).status_code == 422


def test_no_case_writes_and_unknown_case(client, settings):
    headers = bearer(settings, "medical_officer")
    assert client.get("/v1/cases/UNKNOWN", headers=headers).status_code == 404
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/v1/cases/GOL001", headers=headers).status_code == 405


def test_repository_tenant_boundary():
    repository = SyntheticCaseRepository()
    assert repository.get_case(uuid4(), "GOL001") is None


def test_synthetic_repository_disabled_outside_local_test(settings, engine):
    from fastapi.testclient import TestClient

    from ciq_api.config import Settings

    config = Settings(
        environment="staging",
        auth_mode="oidc",
        oidc_issuer="https://issuer.example",
        oidc_jwks_url="https://issuer.example/jwks",
    )
    app = create_app(config, engine)
    # Simulate an authenticated OIDC boundary without networking or changing the route guard.
    from ciq_api.contracts import MeResponse, TenantView, UserView

    identity_dependency = (
        next(route for route in app.routes if getattr(route, "path", "") == "/v1/me")
        .dependant.dependencies[0]
        .call
    )
    app.dependency_overrides[identity_dependency] = lambda: MeResponse(
        user=UserView(id=uuid4(), display_name="Synthetic test"),
        tenant=TenantView(id=TENANT_ID, name="Synthetic test"),
        role="medical_officer",
        capabilities=["case:read"],
        identity_mode="oidc",
    )
    with TestClient(app) as http:
        assert http.get("/v1/cases").status_code == 503


def test_read_capability_enforced(settings, engine):
    from fastapi.testclient import TestClient

    from ciq_api.contracts import MeResponse, TenantView, UserView

    app = create_app(settings, engine)
    identity_dependency = (
        next(route for route in app.routes if getattr(route, "path", "") == "/v1/me")
        .dependant.dependencies[0]
        .call
    )
    app.dependency_overrides[identity_dependency] = lambda: MeResponse(
        user=UserView(id=uuid4(), display_name="Synthetic test"),
        tenant=TenantView(id=TENANT_ID, name="Synthetic test"),
        role="auditor",
        capabilities=[],
        identity_mode="local",
    )
    with TestClient(app) as http:
        assert http.get("/v1/cases").status_code == 403
