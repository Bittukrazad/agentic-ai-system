"""app/config.py — Central configuration loaded from .env

Every environment variable used anywhere in the project is declared here.
Agents and tools import `config` from this module — never call os.getenv
directly from business logic files.

Priority (highest → lowest):
  1. Real environment variables (set by the shell / Docker / secrets manager)
  2. .env file in the project root
  3. Default values defined in this file
"""
import os
from dotenv import load_dotenv

load_dotenv(override=False)


class Config:

    # ── LLM ──────────────────────────────────────────────────────────────────
    OPENAI_API_KEY:     str   = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY:  str   = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_PROVIDER:       str   = os.getenv("LLM_PROVIDER", "mock").lower()
    LLM_MODEL:          str   = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_MAX_TOKENS:     int   = int(os.getenv("LLM_MAX_TOKENS", "1500"))

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL:       str   = os.getenv("DATABASE_URL", "sqlite:///./agentic_ai.db")

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL:          str   = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED:      bool  = os.getenv("REDIS_ENABLED", "false").lower() == "true"

    # ── Slack ─────────────────────────────────────────────────────────────────
    SLACK_BOT_TOKEN:          str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL:            str = os.getenv("SLACK_CHANNEL", "#enterprise-alerts")
    SLACK_ESCALATION_CHANNEL: str = os.getenv("SLACK_ESCALATION_CHANNEL", "#manager-alerts")
    SLACK_HEALTH_CHANNEL:     str = os.getenv("SLACK_HEALTH_CHANNEL", "#workflow-health")
    SLACK_WORKSPACE:          str = os.getenv("SLACK_WORKSPACE", "")

    # ── Email (SMTP) ──────────────────────────────────────────────────────────
    SMTP_HOST:          str   = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT:          int   = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USE_TLS:       bool  = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USER:          str   = os.getenv("SMTP_USER", "")
    SMTP_PASS:          str   = os.getenv("SMTP_PASS", "")
    SMTP_FROM_NAME:     str   = os.getenv("SMTP_FROM_NAME", "Agentic AI System")
    MANAGER_EMAIL:      str   = os.getenv("MANAGER_EMAIL", "manager@company.com")
    ADMIN_EMAIL:        str   = os.getenv("ADMIN_EMAIL", "admin@company.com")

    # ── Google Calendar ───────────────────────────────────────────────────────
    GOOGLE_CALENDAR_CREDENTIALS: str = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")
    GOOGLE_CALENDAR_TOKEN:        str = os.getenv("GOOGLE_CALENDAR_TOKEN", "./google_token.json")
    GOOGLE_CALENDAR_ID:           str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    # ── External Enterprise APIs ──────────────────────────────────────────────
    HRMS_API_URL:         str   = os.getenv("HRMS_API_URL", "")
    HRMS_API_KEY:         str   = os.getenv("HRMS_API_KEY", "")
    ERP_API_URL:          str   = os.getenv("ERP_API_URL", "")
    ERP_API_KEY:          str   = os.getenv("ERP_API_KEY", "")
    CRM_API_URL:          str   = os.getenv("CRM_API_URL", "")
    CRM_API_KEY:          str   = os.getenv("CRM_API_KEY", "")
    EXTERNAL_API_TIMEOUT: int   = int(os.getenv("EXTERNAL_API_TIMEOUT", "30"))

    # ── Agent Behaviour Tuning ────────────────────────────────────────────────
    CONFIDENCE_THRESHOLD:  float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
    MAX_RETRIES:           int   = int(os.getenv("MAX_RETRIES", "3"))
    SLA_TIMEOUT_MINUTES:   int   = int(os.getenv("SLA_TIMEOUT_MINUTES", "30"))
    BASE_RETRY_DELAY:      float = float(os.getenv("BASE_RETRY_DELAY", "1.0"))
    MAX_RETRY_DELAY:       float = float(os.getenv("MAX_RETRY_DELAY", "30.0"))

    SLA_MEETING_HOURS:     int   = int(os.getenv("SLA_MEETING_HOURS",     "1"))
    SLA_ONBOARDING_HOURS:  int   = int(os.getenv("SLA_ONBOARDING_HOURS",  "48"))
    SLA_PROCUREMENT_HOURS: int   = int(os.getenv("SLA_PROCUREMENT_HOURS", "72"))
    SLA_CONTRACT_HOURS:    int   = int(os.getenv("SLA_CONTRACT_HOURS",    "96"))

    # ── Health Monitoring ─────────────────────────────────────────────────────
    HEALTH_CHECK_INTERVAL_MINUTES:    int   = int(os.getenv("HEALTH_CHECK_INTERVAL_MINUTES", "5"))
    DRIFT_MULTIPLIER:                 float = float(os.getenv("DRIFT_MULTIPLIER", "1.5"))
    BREACH_TRIGGER_THRESHOLD:         float = float(os.getenv("BREACH_TRIGGER_THRESHOLD", "0.70"))
    ANOMALY_RETRY_THRESHOLD:          int   = int(os.getenv("ANOMALY_RETRY_THRESHOLD", "3"))
    ANOMALY_ERROR_THRESHOLD:          int   = int(os.getenv("ANOMALY_ERROR_THRESHOLD", "2"))
    CIRCUIT_BREAKER_THRESHOLD:        int   = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
    CIRCUIT_BREAKER_RECOVERY_SECONDS: float = float(os.getenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "60"))

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL:           str   = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT:          str   = os.getenv("LOG_FORMAT", "text").lower()
    LOG_FILE:            str   = os.getenv("LOG_FILE", "")
    LOG_INCLUDE_CONTEXT: bool  = os.getenv("LOG_INCLUDE_CONTEXT", "true").lower() == "true"

    # ── Application Server ────────────────────────────────────────────────────
    APP_HOST:           str   = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT:           int   = int(os.getenv("APP_PORT", "8000"))
    DEBUG:              bool  = os.getenv("DEBUG", "true").lower() == "true"
    WORKERS:            int   = int(os.getenv("WORKERS", "1"))
    REQUEST_TIMEOUT:    int   = int(os.getenv("REQUEST_TIMEOUT", "60"))
    DASHBOARD_PORT:     int   = int(os.getenv("DASHBOARD_PORT", "8501"))
    CORS_ORIGINS:       str   = os.getenv("CORS_ORIGINS", "*")

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY:              str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    API_KEY:                 str = os.getenv("API_KEY", "")
    RATE_LIMIT_PER_MINUTE:   int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "0"))

    # ── Derived helpers ───────────────────────────────────────────────────────
    @classmethod
    def is_mock_llm(cls) -> bool:
        return cls.LLM_PROVIDER == "mock"

    @classmethod
    def slack_enabled(cls) -> bool:
        return bool(cls.SLACK_BOT_TOKEN and cls.SLACK_BOT_TOKEN.startswith("xoxb-"))

    @classmethod
    def email_enabled(cls) -> bool:
        return bool(cls.SMTP_USER and cls.SMTP_PASS)

    @classmethod
    def calendar_enabled(cls) -> bool:
        return bool(cls.GOOGLE_CALENDAR_CREDENTIALS)

    @classmethod
    def sla_hours(cls, workflow_type: str) -> int:
        return {
            "meeting":     cls.SLA_MEETING_HOURS,
            "onboarding":  cls.SLA_ONBOARDING_HOURS,
            "procurement": cls.SLA_PROCUREMENT_HOURS,
            "contract":    cls.SLA_CONTRACT_HOURS,
        }.get(workflow_type, 24)

    @classmethod
    def summary(cls) -> dict:
        """Return a safe (no secrets) summary of the active configuration."""
        return {
            "llm_provider":         cls.LLM_PROVIDER,
            "llm_model":            cls.LLM_MODEL,
            "database":             cls.DATABASE_URL.split("://")[0],
            "redis_enabled":        cls.REDIS_ENABLED,
            "slack_enabled":        cls.slack_enabled(),
            "email_enabled":        cls.email_enabled(),
            "calendar_enabled":     cls.calendar_enabled(),
            "confidence_threshold": cls.CONFIDENCE_THRESHOLD,
            "max_retries":          cls.MAX_RETRIES,
            "sla_timeout_minutes":  cls.SLA_TIMEOUT_MINUTES,
            "log_level":            cls.LOG_LEVEL,
            "debug":                cls.DEBUG,
        }


config = Config()
