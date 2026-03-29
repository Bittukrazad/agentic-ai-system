"""tests/test_config.py — Tests for app/config.py and .env files"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestConfigDefaults(unittest.TestCase):
    """Config loads correct defaults when no .env is present."""

    def setUp(self):
        # Wipe any loaded env vars that would interfere
        for key in ["LLM_PROVIDER", "LLM_MAX_TOKENS", "MAX_RETRIES",
                    "CONFIDENCE_THRESHOLD", "DEBUG", "REDIS_ENABLED",
                    "SMTP_USE_TLS", "LOG_INCLUDE_CONTEXT"]:
            os.environ.pop(key, None)

        # Force reimport with clean state
        import importlib
        import app.config as cfg_module
        importlib.reload(cfg_module)
        from app.config import Config
        self.Config = Config

    def test_default_llm_provider_is_mock(self):
        self.assertEqual(self.Config.LLM_PROVIDER, "mock")

    def test_default_database_is_sqlite(self):
        self.assertIn("sqlite", self.Config.DATABASE_URL)

    def test_default_confidence_threshold(self):
        self.assertAlmostEqual(self.Config.CONFIDENCE_THRESHOLD, 0.7)

    def test_default_max_retries(self):
        self.assertEqual(self.Config.MAX_RETRIES, 3)

    def test_default_sla_timeout(self):
        self.assertEqual(self.Config.SLA_TIMEOUT_MINUTES, 30)

    def test_default_health_interval(self):
        self.assertEqual(self.Config.HEALTH_CHECK_INTERVAL_MINUTES, 5)

    def test_default_log_level(self):
        self.assertEqual(self.Config.LOG_LEVEL, "INFO")

    def test_default_app_port(self):
        self.assertEqual(self.Config.APP_PORT, 8000)

    def test_default_dashboard_port(self):
        self.assertEqual(self.Config.DASHBOARD_PORT, 8501)

    def test_default_redis_disabled(self):
        self.assertFalse(self.Config.REDIS_ENABLED)

    def test_default_workers(self):
        self.assertEqual(self.Config.WORKERS, 1)

    def test_default_llm_max_tokens(self):
        self.assertEqual(self.Config.LLM_MAX_TOKENS, 1500)

    def test_default_drift_multiplier(self):
        self.assertAlmostEqual(self.Config.DRIFT_MULTIPLIER, 1.5)

    def test_default_breach_threshold(self):
        self.assertAlmostEqual(self.Config.BREACH_TRIGGER_THRESHOLD, 0.70)

    def test_default_external_api_timeout(self):
        self.assertEqual(self.Config.EXTERNAL_API_TIMEOUT, 30)

    def test_default_smtp_port(self):
        self.assertEqual(self.Config.SMTP_PORT, 587)

    def test_default_manager_email(self):
        self.assertIn("@", self.Config.MANAGER_EMAIL)

    def test_default_cors_origins(self):
        self.assertEqual(self.Config.CORS_ORIGINS, "*")


class TestConfigEnvOverride(unittest.TestCase):
    """Config reads and casts environment variable overrides correctly."""

    def _reload(self):
        import importlib
        import app.config as cfg_module
        importlib.reload(cfg_module)
        return cfg_module.Config

    def test_llm_provider_override(self):
        os.environ["LLM_PROVIDER"] = "anthropic"
        Config = self._reload()
        self.assertEqual(Config.LLM_PROVIDER, "anthropic")
        os.environ.pop("LLM_PROVIDER")

    def test_confidence_threshold_cast_to_float(self):
        os.environ["CONFIDENCE_THRESHOLD"] = "0.85"
        Config = self._reload()
        self.assertIsInstance(Config.CONFIDENCE_THRESHOLD, float)
        self.assertAlmostEqual(Config.CONFIDENCE_THRESHOLD, 0.85)
        os.environ.pop("CONFIDENCE_THRESHOLD")

    def test_max_retries_cast_to_int(self):
        os.environ["MAX_RETRIES"] = "5"
        Config = self._reload()
        self.assertIsInstance(Config.MAX_RETRIES, int)
        self.assertEqual(Config.MAX_RETRIES, 5)
        os.environ.pop("MAX_RETRIES")

    def test_debug_bool_true(self):
        os.environ["DEBUG"] = "true"
        Config = self._reload()
        self.assertIs(Config.DEBUG, True)
        os.environ.pop("DEBUG")

    def test_debug_bool_false(self):
        os.environ["DEBUG"] = "false"
        Config = self._reload()
        self.assertIs(Config.DEBUG, False)
        os.environ.pop("DEBUG")

    def test_redis_enabled_bool(self):
        os.environ["REDIS_ENABLED"] = "true"
        Config = self._reload()
        self.assertIs(Config.REDIS_ENABLED, True)
        os.environ.pop("REDIS_ENABLED")

    def test_log_level_uppercased(self):
        os.environ["LOG_LEVEL"] = "debug"
        Config = self._reload()
        self.assertEqual(Config.LOG_LEVEL, "DEBUG")
        os.environ.pop("LOG_LEVEL")

    def test_llm_max_tokens_override(self):
        os.environ["LLM_MAX_TOKENS"] = "2000"
        Config = self._reload()
        self.assertEqual(Config.LLM_MAX_TOKENS, 2000)
        os.environ.pop("LLM_MAX_TOKENS")

    def test_sla_meeting_hours_override(self):
        os.environ["SLA_MEETING_HOURS"] = "2"
        Config = self._reload()
        self.assertEqual(Config.SLA_MEETING_HOURS, 2)
        os.environ.pop("SLA_MEETING_HOURS")


class TestConfigDerivedHelpers(unittest.TestCase):
    """Test the helper classmethods on Config."""

    def setUp(self):
        import importlib
        import app.config as cfg_module
        importlib.reload(cfg_module)
        from app.config import Config
        self.Config = Config

    def test_is_mock_llm_true(self):
        os.environ["LLM_PROVIDER"] = "mock"
        import importlib
        import app.config as m
        importlib.reload(m)
        self.assertTrue(m.Config.is_mock_llm())
        os.environ.pop("LLM_PROVIDER")

    def test_slack_disabled_without_token(self):
        # No real token set
        self.assertFalse(self.Config.slack_enabled())

    def test_slack_enabled_with_real_token(self):
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-fake-token-for-test"
        import importlib
        import app.config as m
        importlib.reload(m)
        self.assertTrue(m.Config.slack_enabled())
        os.environ.pop("SLACK_BOT_TOKEN")

    def test_email_disabled_without_credentials(self):
        self.assertFalse(self.Config.email_enabled())

    def test_calendar_disabled_without_credentials(self):
        self.assertFalse(self.Config.calendar_enabled())

    def test_sla_hours_meeting(self):
        self.assertEqual(self.Config.sla_hours("meeting"), self.Config.SLA_MEETING_HOURS)

    def test_sla_hours_onboarding(self):
        self.assertEqual(self.Config.sla_hours("onboarding"), self.Config.SLA_ONBOARDING_HOURS)

    def test_sla_hours_procurement(self):
        self.assertEqual(self.Config.sla_hours("procurement"), self.Config.SLA_PROCUREMENT_HOURS)

    def test_sla_hours_contract(self):
        self.assertEqual(self.Config.sla_hours("contract"), self.Config.SLA_CONTRACT_HOURS)

    def test_sla_hours_unknown_defaults_to_24(self):
        self.assertEqual(self.Config.sla_hours("unknown_workflow"), 24)

    def test_summary_returns_dict(self):
        summary = self.Config.summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("llm_provider", summary)
        self.assertIn("log_level", summary)

    def test_summary_has_no_secrets(self):
        summary = self.Config.summary()
        # Keys that hold secrets must NOT appear in summary
        for secret_key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                            "SMTP_PASS", "SECRET_KEY", "API_KEY"]:
            self.assertNotIn(secret_key, summary)
            self.assertNotIn(secret_key.lower(), summary)

    def test_summary_database_shows_only_scheme(self):
        summary = self.Config.summary()
        # Should show "sqlite" not the full connection string
        self.assertIn(summary["database"], ["sqlite", "postgresql", "mysql"])


class TestEnvFiles(unittest.TestCase):
    """Verify .env files exist and have expected structure."""

    BASE = os.path.join(os.path.dirname(__file__), "..")

    def _load_env_file(self, filename: str) -> dict:
        """Parse a .env file into a dict."""
        path = os.path.join(self.BASE, filename)
        if not os.path.exists(path):
            return {}
        result = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip()
        return result

    def test_env_example_exists(self):
        path = os.path.join(self.BASE, ".env.example")
        self.assertTrue(os.path.exists(path), ".env.example not found")

    def test_env_development_exists(self):
        path = os.path.join(self.BASE, ".env.development")
        self.assertTrue(os.path.exists(path), ".env.development not found")

    def test_env_production_exists(self):
        path = os.path.join(self.BASE, ".env.production")
        self.assertTrue(os.path.exists(path), ".env.production not found")

    def test_env_test_exists(self):
        path = os.path.join(self.BASE, ".env.test")
        self.assertTrue(os.path.exists(path), ".env.test not found")

    def test_env_example_has_required_keys(self):
        env = self._load_env_file(".env.example")
        required = [
            "LLM_PROVIDER", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            "LLM_MODEL", "LLM_MAX_TOKENS",
            "DATABASE_URL", "REDIS_URL", "REDIS_ENABLED",
            "SLACK_BOT_TOKEN", "SLACK_CHANNEL",
            "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS",
            "GOOGLE_CALENDAR_CREDENTIALS",
            "HRMS_API_URL", "ERP_API_URL", "CRM_API_URL",
            "CONFIDENCE_THRESHOLD", "MAX_RETRIES", "SLA_TIMEOUT_MINUTES",
            "BASE_RETRY_DELAY", "MAX_RETRY_DELAY",
            "SLA_MEETING_HOURS", "SLA_ONBOARDING_HOURS",
            "SLA_PROCUREMENT_HOURS", "SLA_CONTRACT_HOURS",
            "HEALTH_CHECK_INTERVAL_MINUTES", "DRIFT_MULTIPLIER",
            "BREACH_TRIGGER_THRESHOLD",
            "LOG_LEVEL", "LOG_FORMAT",
            "APP_HOST", "APP_PORT", "DEBUG", "WORKERS",
            "DASHBOARD_PORT", "CORS_ORIGINS",
            "SECRET_KEY", "API_KEY",
        ]
        for key in required:
            self.assertIn(key, env, f"Missing from .env.example: {key}")

    def test_env_development_uses_mock_llm(self):
        env = self._load_env_file(".env.development")
        self.assertEqual(env.get("LLM_PROVIDER"), "mock")

    def test_env_development_sqlite(self):
        env = self._load_env_file(".env.development")
        self.assertIn("sqlite", env.get("DATABASE_URL", ""))

    def test_env_development_redis_disabled(self):
        env = self._load_env_file(".env.development")
        self.assertEqual(env.get("REDIS_ENABLED", "").lower(), "false")

    def test_env_development_debug_true(self):
        env = self._load_env_file(".env.development")
        self.assertEqual(env.get("DEBUG", "").lower(), "true")

    def test_env_production_uses_real_llm(self):
        env = self._load_env_file(".env.production")
        self.assertNotEqual(env.get("LLM_PROVIDER"), "mock")

    def test_env_production_redis_enabled(self):
        env = self._load_env_file(".env.production")
        self.assertEqual(env.get("REDIS_ENABLED", "").lower(), "true")

    def test_env_production_debug_false(self):
        env = self._load_env_file(".env.production")
        self.assertEqual(env.get("DEBUG", "").lower(), "false")

    def test_env_production_log_level_warning(self):
        env = self._load_env_file(".env.production")
        self.assertEqual(env.get("LOG_LEVEL", "").upper(), "WARNING")

    def test_env_test_mock_llm(self):
        env = self._load_env_file(".env.test")
        self.assertEqual(env.get("LLM_PROVIDER"), "mock")

    def test_env_test_fast_retry_delay(self):
        env = self._load_env_file(".env.test")
        delay = float(env.get("BASE_RETRY_DELAY", "999"))
        self.assertLess(delay, 1.0)

    def test_env_test_fast_sla_timeout(self):
        env = self._load_env_file(".env.test")
        timeout = int(env.get("SLA_TIMEOUT_MINUTES", "999"))
        self.assertLess(timeout, 10)

    def test_all_env_files_have_same_keys(self):
        """Every key in .env.example should exist in .env.development and .env.test."""
        example = self._load_env_file(".env.example")
        development = self._load_env_file(".env.development")
        test_env = self._load_env_file(".env.test")

        for key in example:
            self.assertIn(key, development,
                          f"Key '{key}' in .env.example but missing from .env.development")
            self.assertIn(key, test_env,
                          f"Key '{key}' in .env.example but missing from .env.test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
