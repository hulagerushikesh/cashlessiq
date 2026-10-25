"""Explicit environment configuration with fail-closed identity defaults."""

from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CIQ_", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: SecretStr = SecretStr("postgresql+psycopg://localhost/cashlessiq")
    auth_mode: Literal["local", "oidc"] = "oidc"
    local_auth_secret: SecretStr = SecretStr("")
    oidc_issuer: str = ""
    oidc_audience: str = "cashlessiq-api"
    oidc_jwks_url: str = ""
    synthetic_workflows: bool = False
    local_embedded_worker: bool = False

    @model_validator(mode="after")
    def validate_auth(self) -> "Settings":
        if self.local_embedded_worker and not self.synthetic_workflows:
            raise ValueError("Local embedded worker requires synthetic workflows")
        if self.synthetic_workflows and (
            self.environment not in {"local", "test"} or self.auth_mode != "local"
        ):
            raise ValueError("Synthetic workflows require local/test local identity")
        if self.auth_mode == "local":
            if self.environment not in {"local", "test"}:
                raise ValueError("Local identity is allowed only in local/test environments")
            if len(self.local_auth_secret.get_secret_value()) < 32:
                raise ValueError(
                    "Local identity requires a random secret of at least 32 characters"
                )
        elif not (
            self.oidc_issuer.startswith("https://") and self.oidc_jwks_url.startswith("https://")
        ):
            raise ValueError("OIDC requires an HTTPS issuer and JWKS URL")
        return self
