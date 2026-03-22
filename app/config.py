"""
Configuration Module - Environment variables and system configuration.

Provides:
- Environment variable management
- Configuration validation
- Secrets handling
- Default values
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
import os


class Settings(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    """
    Application settings from environment variables.
    
    Uses .env file for local development, environment variables for production.
    """
    
    # Application
    APP_NAME: str = Field(default="Agentic AI System")
    APP_ENV: str = Field(default="development")  # development, staging, production
    DEBUG: bool = Field(default=False)
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_WORKERS: int = Field(default=4)
    CORS_ORIGINS: str = Field(default="*")
    ALLOWED_HOSTS: str = Field(default="*")
    WORKSPACE_NAME: str = Field(default="company")
    
    # Paths
    PROJECT_ROOT: str = Field(default="/d:/prototype/agentic-ai-system")
    WORKFLOWS_DIR: str = Field(default="workflows")
    STATE_STORE_FILE: str = Field(default="memory/workflow_state_store.json")
    
    # Audit Configuration
    AUDIT_DIR: str = Field(default="audit")
    TRACE_LOG_FILE: str = Field(default="audit/trace_logs.jsonl")
    DECISION_LOG_FILE: str = Field(default="audit/decision_logs.jsonl")
    
    # Database
    DB_TYPE: str = Field(default="sqlite")  # sqlite, postgresql, mysql
    DB_CONNECTION_STRING: Optional[str] = Field(default=None)
    
    # LLM Configuration
    LLM_TYPE: str = Field(default="mock")  # mock, openai, anthropic, local
    LLM_API_KEY: Optional[str] = Field(default=None)
    LLM_MODEL: str = Field(default="gpt-4")
    LLM_TEMPERATURE: float = Field(default=0.7)
    LLM_MAX_TOKENS: int = Field(default=2048)
    LLM_TIMEOUT_SECONDS: int = Field(default=30)
    
    # Slack Configuration
    SLACK_BOT_TOKEN: Optional[str] = Field(default=None)
    SLACK_CHANNEL_ID: Optional[str] = Field(default=None)
    SLACK_ENABLED: bool = Field(default=False)
    
    # Email Configuration
    EMAIL_SMTP_HOST: str = Field(default="localhost")
    EMAIL_SMTP_PORT: int = Field(default=587)
    EMAIL_FROM_ADDRESS: str = Field(default="agentic-system@example.com")
    EMAIL_USERNAME: Optional[str] = Field(default=None)
    EMAIL_PASSWORD: Optional[str] = Field(default=None)
    EMAIL_ENABLED: bool = Field(default=False)
    SMTP_USE_TLS: bool = Field(default=True)
    
    # Workflow Configuration
    DEFAULT_STEP_TIMEOUT_SECONDS: int = Field(default=300)
    DEFAULT_STEP_RETRIES: int = Field(default=3)
    DEFAULT_WORKFLOW_SLA_HOURS: float = Field(default=24)
    MAX_WORKFLOW_EXECUTION_TIME_MINUTES: int = Field(default=1440)  # 24 hours
    
    # Agent Configuration
    AGENT_RESPONSE_TIMEOUT_SECONDS: int = Field(default=60)
    MAX_AGENT_RETRIES: int = Field(default=3)
    
    # Monitoring
    ENABLE_HEALTH_CHECK: bool = Field(default=True)
    HEALTH_CHECK_INTERVAL_SECONDS: int = Field(default=60)
    SLA_CHECK_INTERVAL_SECONDS: int = Field(default=600)  # 10 minutes
    BOTTLENECK_DETECTION_ENABLED: bool = Field(default=True)
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT: str = Field(default="json")  # json, text
    
    # Feature Flags
    ENABLE_MEETING_INTELLIGENCE: bool = Field(default=True)
    ENABLE_AUTO_ESCALATION: bool = Field(default=True)
    ENABLE_PROCESS_DRIFT_DETECTION: bool = Field(default=True)
    
    # Cache
    ENABLE_CACHE: bool = Field(default=True)
    CACHE_TTL_SECONDS: int = Field(default=300)  # 5 minutes
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.APP_ENV == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.APP_ENV == "development"
    
    @property
    def api_host(self) -> str:
        """Get API host."""
        return self.API_HOST
    
    @property
    def api_port(self) -> int:
        """Get API port."""
        return self.API_PORT
    
    @property
    def cors_origins(self) -> list:
        """Get CORS origins."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]
    
    @property
    def allowed_hosts(self) -> list:
        """Get allowed hosts."""
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",")]
    
    @property
    def workspace_name(self) -> str:
        """Get workspace name."""
        return self.WORKSPACE_NAME
    
    @property
    def smtp_host(self) -> str:
        """Get SMTP host."""
        return self.EMAIL_SMTP_HOST
    
    @property
    def smtp_port(self) -> int:
        """Get SMTP port."""
        return self.EMAIL_SMTP_PORT
    
    @property
    def smtp_user(self) -> Optional[str]:
        """Get SMTP user."""
        return self.EMAIL_USERNAME
    
    @property
    def smtp_password(self) -> Optional[str]:
        """Get SMTP password."""
        return self.EMAIL_PASSWORD
    
    @property
    def smtp_use_tls(self) -> bool:
        """Get SMTP TLS setting."""
        return self.SMTP_USE_TLS
    
    @property
    def smtp_from_email(self) -> str:
        """Get SMTP from email."""
        return self.EMAIL_FROM_ADDRESS
    
    @property
    def slack_bot_token(self) -> Optional[str]:
        """Get Slack bot token."""
        return self.SLACK_BOT_TOKEN
    
    @property
    def full_workflows_dir(self) -> str:
        """Get full path to workflows directory."""
        from pathlib import Path
        path = Path(self.PROJECT_ROOT) / self.WORKFLOWS_DIR
        return str(path)
    
    @property
    def full_state_store_file(self) -> str:
        """Get full path to state store file."""
        from pathlib import Path
        path = Path(self.PROJECT_ROOT) / self.STATE_STORE_FILE
        return str(path)
    
    @property
    def full_audit_dir(self) -> str:
        """Get full path to audit directory."""
        from pathlib import Path
        path = Path(self.PROJECT_ROOT) / self.AUDIT_DIR
        return str(path)
    
    @property
    def full_trace_log_file(self) -> str:
        """Get full path to trace log file."""
        from pathlib import Path
        path = Path(self.PROJECT_ROOT) / self.TRACE_LOG_FILE
        return str(path)
    
    @property
    def full_decision_log_file(self) -> str:
        """Get full path to decision log file."""
        from pathlib import Path
        path = Path(self.PROJECT_ROOT) / self.DECISION_LOG_FILE
        return str(path)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get global settings instance.
    
    Returns:
        Settings instance
    """
    return settings


def validate_settings() -> bool:
    """
    Validate critical settings.
    
    Returns:
        True if all critical settings are valid
    """
    errors = []
    
    # Check paths exist or can be created
    from pathlib import Path
    
    try:
        Path(settings.full_workflows_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create workflows dir: {e}")
    
    try:
        Path(settings.full_audit_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create audit dir: {e}")
    
    if errors:
        print("Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True
