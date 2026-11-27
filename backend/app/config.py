"""Application settings and fail-closed environment validation."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.workload_limits import (
    EXTENDED_MAX_SERVICES,
    EXTENDED_MAX_STEPS,
    MIN_WORKLOAD_SERVICES,
    MIN_WORKLOAD_STEPS,
)


class Settings(BaseSettings):
    """CloudPilot backend configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "production"] = "development"
    CLOUDPILOT_API_KEY: str = ""
    DEV_AUTH_DISABLED: bool = False
    ALLOWED_ORIGIN: str = "http://localhost:5173"
    RATE_LIMIT_PER_MIN: int = Field(default=30, ge=1)

    # Simulation engine limits
    SIM_MAX_STEPS: int = Field(default=1000, ge=1)
    SIM_MAX_SERVICES: int = Field(default=20, ge=1)
    SIM_TIMEOUT_SECONDS: int = Field(default=42, ge=1)
    SIM_MAX_CONCURRENT: int = Field(default=1, ge=1)
    SIM_RF_JOBS: int = Field(default=1, ge=1)
    SIM_NATIVE_THREADS: int = Field(default=1, ge=1)
    SIM_MAX_RESULT_BYTES: int = Field(default=2_000_000, ge=1, le=4_000_000)
    GLOBAL_SIM_PER_MIN: int = Field(default=20, ge=1)
    ENABLE_EXTENDED_SIMULATION: bool = False
    ENABLE_PRODUCTION_EXTENDED_SIMULATION: bool = False
    SIM_EXTENDED_MAX_SERVICES: int = Field(
        default=4, ge=MIN_WORKLOAD_SERVICES, le=EXTENDED_MAX_SERVICES
    )
    SIM_EXTENDED_MAX_STEPS: int = Field(default=600, ge=MIN_WORKLOAD_STEPS, le=EXTENDED_MAX_STEPS)

    # Optional Supabase integration for traces & persistence
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None

    # Maximum request body size in bytes (1 MB)
    MAX_REQUEST_BODY_BYTES: int = 1024 * 1024

    @model_validator(mode="after")
    def validate_fail_closed(self) -> Settings:
        """Enforce strict fail-closed security rules across environments."""
        key = self.CLOUDPILOT_API_KEY.strip()
        origins = self.ALLOWED_ORIGIN.strip()

        if self.APP_ENV == "production":
            if not key or len(key) < 32:
                raise ValueError(
                    "Production requires CLOUDPILOT_API_KEY to be set "
                    "and at least 32 characters long."
                )
            if not origins or "*" in origins:
                raise ValueError(
                    "Production requires ALLOWED_ORIGIN to be set and cannot contain wildcard '*'."
                )
            if not self.SUPABASE_URL or not self.SUPABASE_URL.strip().startswith("https://"):
                raise ValueError(
                    "Production requires SUPABASE_URL to be set with an https:// scheme."
                )
            if not self.SUPABASE_SERVICE_KEY or not self.SUPABASE_SERVICE_KEY.strip():
                raise ValueError("Production requires SUPABASE_SERVICE_KEY to be set.")
        else:
            # In development, missing/short key is allowed only if DEV_AUTH_DISABLED is true
            if (not key or len(key) < 32) and not self.DEV_AUTH_DISABLED:
                raise ValueError(
                    "CLOUDPILOT_API_KEY is missing or shorter than 32 chars. "
                    "Set a valid key or explicitly set DEV_AUTH_DISABLED=true in development."
                )

        return self

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.ALLOWED_ORIGIN.split(",") if origin.strip()]

    @property
    def extended_simulation_enabled(self) -> bool:
        if self.APP_ENV == "production":
            return self.ENABLE_PRODUCTION_EXTENDED_SIMULATION
        return self.ENABLE_EXTENDED_SIMULATION

    def simulation_caps(self, extended: bool) -> tuple[int, int]:
        if extended:
            return self.SIM_EXTENDED_MAX_SERVICES, self.SIM_EXTENDED_MAX_STEPS
        return self.SIM_MAX_SERVICES, self.SIM_MAX_STEPS

    @property
    def worker_timeout_seconds(self) -> int:
        # Existing Render instances may retain an older dashboard environment value.
        return (
            min(self.SIM_TIMEOUT_SECONDS, 42)
            if self.APP_ENV == "production"
            else self.SIM_TIMEOUT_SECONDS
        )

    def is_ready(self) -> tuple[bool, str]:
        """Readiness check verifying current configuration state."""
        try:
            self.validate_fail_closed()
            return True, "Configuration is valid"
        except ValueError as exc:
            return False, str(exc)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
