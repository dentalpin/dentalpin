"""Application configuration via environment variables."""

import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    # Independent secret used to sign the public-budget verification
    # cookies (ADR 0006). Falls back to ``SECRET_KEY`` for local/dev
    # convenience, but production deploys must set it explicitly so a
    # leak of one key does not compromise the other.
    BUDGET_PUBLIC_SECRET_KEY: str = ""

    # Environment
    ENVIRONMENT: str = "development"
    # Public demo instance: blocks operations that would lock out or break
    # the shared demo (user edits/removal, module install/uninstall/restart).
    DEMO_MODE: bool = False
    ALLOWED_ORIGINS: str = ""

    # Rate limiting
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "3/hour"

    # Testing
    TESTING: bool = False

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
    # Razorpay online payments (payments module). Key ID is handed to the
    # client SDK; the secret stays server-side for order creation and
    # signature verification. Optional — payments fall back to offline
    # methods when unset.
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
