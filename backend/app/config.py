"""Application configuration via environment variables."""

import warnings
from pathlib import Path
from typing import ClassVar

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32

# Prefixes and names the root .env legitimately carries for its other two
# readers (docker compose interpolation, Nuxt). Anything outside this set
# that is not a Settings field is almost certainly a misspelled app
# setting, which ``extra="ignore"`` would otherwise swallow in silence.
FOREIGN_ENV_PREFIXES = ("POSTGRES_", "NUXT_", "DENTALPIN_", "SEED_", "COMPOSE_", "VITE_")
# FORWARDED_ALLOW_IPS is uvicorn's, not ours (#623): uvicorn reads it
# directly when --forwarded-allow-ips is absent, so it belongs in the
# templates without being a Settings field.
FOREIGN_ENV_KEYS = frozenset({"API_BASE_URL", "PUBLIC_URL", "PATH", "PWD", "FORWARDED_ALLOW_IPS"})


def unknown_env_keys(env_file: str | Path, declared: set[str]) -> list[str]:
    """Keys set in ``env_file`` that are neither app settings nor foreign.

    Pure and path-relative so it can be tested without constructing a
    ``Settings``; returns [] when the file is absent, which is the normal
    case in a container (no .env, only injected variables).
    """
    path = Path(env_file)
    if not path.is_file():
        return []
    # pydantic-settings matches .env keys case-insensitively (case_sensitive=False).
    declared_ci = {name.lower() for name in declared}
    found: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key or key.lower() in declared_ci or key in FOREIGN_ENV_KEYS:
            continue
        if key.startswith(FOREIGN_ENV_PREFIXES):
            continue
        found.append(key)
    return sorted(set(found))


def warn_unknown_env_keys(env_file: str | Path, declared: set[str]) -> None:
    unknown = unknown_env_keys(env_file, declared)
    if unknown:
        warnings.warn(
            f"{env_file} sets keys this application does not declare: "
            f"{', '.join(unknown)}. They are ignored. If one of them is a misspelled "
            "setting, its value is not being applied.",
            stacklevel=2,
        )


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Session cookies (ADR 0023) are host-only by default, which is what a
    # single-host deployment and the e2e stack need. Split-host topologies
    # (app on demo.example.com, API on api-demo.example.com) set the shared
    # parent domain, e.g. ".example.com", so the browser sends the cookies
    # to both hosts and the app can read ``dp_csrf``.
    COOKIE_DOMAIN: str = ""
    # Sistema Tessera Sanitaria (sistema_ts module): the *test* service
    # (invioSS730pTest) presents a certificate issued by the private "Sogei
    # Certification Authority Test", which no public trust store carries, so
    # TLS verification fails until the operator points this at a PEM bundle
    # holding that CA (downloadable from the Sistema TS portal). Production
    # (invioSS730p) chains to a public CA and needs nothing. Empty = the
    # default certifi bundle.
    SISTEMA_TS_CA_BUNDLE: str = ""
    # Presenting a refresh token revoked less than this many seconds ago
    # (two tabs refreshing at once, a Nuxt error re-render) answers with the
    # live successor instead of burning the family (#421). 0 disables.
    REFRESH_REUSE_GRACE_SECONDS: int = 30
    ALGORITHM: str = "HS256"
    # Independent secret used to sign the public-budget verification
    # cookies (ADR 0006). Falls back to ``SECRET_KEY`` for local/dev
    # convenience, but production deploys must set it explicitly so a
    # leak of one key does not compromise the other.
    BUDGET_PUBLIC_SECRET_KEY: str = ""
    # Independent secret used to sign QR check-in tokens (agenda). Falls
    # back to ``SECRET_KEY`` for local/dev convenience, but production
    # deploys must set it explicitly so a printed token never shares a
    # key with the session tokens.
    AGENDA_PUBLIC_SECRET_KEY: str = ""

    # Environment
    ENVIRONMENT: str = "development"
    # Public demo instance: blocks operations that would lock out or break
    # the shared demo (user edits/removal, module install/uninstall/restart).
    DEMO_MODE: bool = False
    ALLOWED_ORIGINS: str = ""

    # Rate limiting
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "3/hour"

    # Leads module — public intake endpoint (/api/v1/leads/public/intake).
    # Only the request size ceiling lives here: it is an operator concern, not
    # a business decision. The daily cap is a per-clinic leads_settings column
    # edited at Settings → Integrations → "Formulario web" — deliberately not
    # an env var (two sources of truth guarantee a support call where the UI
    # says 200 and the process says 50).
    LEADS_INTAKE_MAX_BODY_KB: int = 8

    # Testing
    TESTING: bool = False
    # RBAC source of truth. When False (default), permission checks use the
    # legacy static grant map and custom roles cannot be assigned. When True,
    # require_permission resolves through the DB-backed, clinic-aware tables
    # (roles/role_permissions/permissions/clinic_role_overrides, issue #46)
    # populated by the seed_rbac seeder at every boot.
    RBAC_FROM_DB: bool = False

    # Error tracking (Sentry protocol; self-hosted GlitchTip speaks it too).
    # Unset by default — the app runs without any error reporter. Set
    # SENTRY_DSN in the environment (never committed) to enable. No patient
    # data is attached: send_default_pii stays off and URLs are scrubbed,
    # see setup_error_tracking. Performance tracing is a separate opt-in
    # (0.0 = off): spans carry SQL statement text.
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    # WebPush (notifications push channel). One VAPID pair per deployment:
    # set DENTALPIN_VAPID_PRIVATE_KEY (PEM, env only) + DENTALPIN_VAPID_SUBJECT
    # (mailto contact). Unset = push channel resolves nothing.
    DENTALPIN_VAPID_PRIVATE_KEY: str = ""
    DENTALPIN_VAPID_SUBJECT: str = "mailto:admin@localhost"

    # Module system
    DENTALPIN_DEV_MODULE_SCAN: bool = True  # Fallback filesystem scan for dev
    # Host-mounted path where `frontend/modules.json` lives. The backend
    # writes this file whenever a module with a Nuxt layer is
    # installed/uninstalled so the Nuxt host picks up `extends` on next
    # build. docker-compose mounts `./frontend` → `/host_frontend`.
    DENTALPIN_FRONTEND_ROOT: str = "/host_frontend"
    # Absolute path INSIDE the frontend container where
    # `backend/app/modules` is mounted (see docker-compose). The writer
    # uses this prefix when rendering layer paths in `modules.json` so
    # the frontend container can resolve them with `extends`. In
    # production (single container / bundled deploy) this can be set to
    # the same path the backend sees for modules, in which case no
    # translation happens.
    DENTALPIN_MODULE_LAYERS_MOUNT: str = "/module_layers"
    # The backend-container path at which module packages live. Stripped
    # from absolute layer paths before the MOUNT prefix is applied. Rare
    # to override; exists for non-standard container layouts.
    DENTALPIN_MODULE_PKG_ROOT: str = "/app/app/modules"

    # Storage configuration
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "/app/storage"
    STORAGE_MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    STORAGE_ALLOWED_MIME_TYPES: str = "application/pdf,image/jpeg,image/png"

    @property
    def storage_allowed_mime_types_list(self) -> list[str]:
        """Parse allowed MIME types as list."""
        return [t.strip() for t in self.STORAGE_ALLOWED_MIME_TYPES.split(",")]

    # Email configuration
    EMAIL_ENABLED: bool = True
    EMAIL_PROVIDER: str = "console"  # console, smtp (sendgrid, mailgun in future)

    # SMTP configuration
    EMAIL_SMTP_HOST: str = "smtp.gmail.com"
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_TLS: bool = True
    EMAIL_SMTP_USER: str = ""
    EMAIL_SMTP_PASSWORD: str = ""

    # Default sender
    EMAIL_FROM_ADDRESS: str = "noreply@dentalpin.com"
    EMAIL_FROM_NAME: str = "DentalPin"

    # Copilot / agentic layer (app/core/llm/). OpenAI and Anthropic are
    # the live providers; per-clinic `copilot_settings` overrides
    # provider + model.
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    COPILOT_PROVIDER_DEFAULT: str = "openai"
    COPILOT_MODEL_CHAT_OPENAI: str = "gpt-5.4-mini"
    COPILOT_MODEL_CHAT_ANTHROPIC: str = "claude-sonnet-5"
    COPILOT_MAX_TOKENS: int = 4096
    COPILOT_REDACTION_DEFAULT: bool = True

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS as comma-separated list."""
        if not self.ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @model_validator(mode="after")
    def _validate_secret_key_strength(self) -> "Settings":
        """Reject a weak SECRET_KEY in production; warn everywhere else.

        SECRET_KEY signs JWTs and derives the Fernet key used to encrypt
        SMTP passwords and Veri*Factu tax certificates at rest (see
        GHSA-hcg9-cm67-2g8f) — a short/weak value compromises all three.
        A model_validator (not a field_validator on SECRET_KEY) is used
        because ENVIRONMENT is declared after SECRET_KEY, so a
        field_validator's `info.data` would not see it yet.
        """
        if len(self.SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
            message = (
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} "
                "characters (see .env.example: openssl rand -hex 32)."
            )
            if self.ENVIRONMENT == "production":
                raise ValueError(message)
            warnings.warn(message, stacklevel=2)
        return self

    @model_validator(mode="after")
    def _validate_public_secret_key(self) -> "Settings":
        """Require a dedicated public-link key in production (#538).

        Public budget sessions must never be signed with the staff-JWT
        key, so a production boot without ``BUDGET_PUBLIC_SECRET_KEY``
        fails here with an actionable message instead of serving the
        first patient a 500 from the request-time check.
        """
        key = self.BUDGET_PUBLIC_SECRET_KEY or ""
        if self.ENVIRONMENT != "production":
            return self
        stripped_key = key.strip()
        if not key:
            raise ValueError(
                "BUDGET_PUBLIC_SECRET_KEY is required in production: refusing "
                "to start with public budget sessions bound to the staff-JWT "
                "SECRET_KEY."
            )
        if not stripped_key:
            raise ValueError(
                "BUDGET_PUBLIC_SECRET_KEY must not be blank or whitespace in "
                "production: refusing to start with a signing key that has no "
                "entropy."
            )
        if key != stripped_key:
            raise ValueError(
                "BUDGET_PUBLIC_SECRET_KEY must not have leading or trailing "
                "whitespace in production: the validator checks the stripped "
                "value, while signing uses the configured value."
            )
        if len(stripped_key) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"BUDGET_PUBLIC_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} "
                "characters (see .env.example: openssl rand -hex 32)."
            )
        return self

    #: Valid ENVIRONMENT values (#530). Anything else (a typo like
    #: "prod", "staging") fails fast at boot instead of silently
    #: degrading production-only behavior (docs, secure cookies,
    #: limiters) to development defaults.
    VALID_ENVIRONMENTS: ClassVar[tuple[str, ...]] = ("development", "test", "production")

    @model_validator(mode="after")
    def _validate_environment(self) -> "Settings":
        """Reject unknown ENVIRONMENT values at boot."""
        if self.ENVIRONMENT not in self.VALID_ENVIRONMENTS:
            raise ValueError(
                f"ENVIRONMENT must be one of {list(self.VALID_ENVIRONMENTS)}, "
                f"got {self.ENVIRONMENT!r}."
            )
        return self

    @model_validator(mode="after")
    def _warn_about_unknown_env_keys(self) -> "Settings":
        """Name keys in ``.env`` that look like misspelled app settings.

        ``extra="ignore"`` is required because the root ``.env`` is shared
        with docker compose and Nuxt, but it also means a typo in an app
        setting is dropped without a word: write ``SENTRY_DNS`` and
        ``SENTRY_DSN`` stays empty, so error tracking is silently off and
        nothing says why. Boot still succeeds; this only reports, once,
        that a key was not recognised.
        """
        env_file = self.model_config.get("env_file")
        if env_file:
            warn_unknown_env_keys(env_file, set(type(self).model_fields))
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # The root .env serves three masters: docker compose interpolates it,
        # Nuxt reads NUXT_* from it, and this model reads it. pydantic-settings
        # v2 defaults to extra="forbid", so every key that exists for the other
        # two consumers made ``import app.config`` fail for anyone running the
        # backend locally — and .env.example itself ships four such keys
        # (POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD / API_BASE_URL), so
        # the documented `cp .env.example .env` + local-backend path was broken
        # on a clean checkout, not just on a customised .env.
        #
        # The container path is unaffected: it has no .env, only env vars
        # compose injects, and every one of those is a field here. Required
        # fields stay required and the production SECRET_KEY check is
        # untouched; only unknown keys are tolerated. The trade-off is that a
        # typo in an app setting is now ignored instead of raising, which is
        # the lesser failure next to not booting at all.
        extra="ignore",
    )


settings = Settings()
