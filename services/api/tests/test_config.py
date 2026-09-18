from packages.config.nexus_config import NexusSettings


def test_nexus_settings_defaults():
    settings = NexusSettings()
    assert settings.api_port == 8000
    assert "http://localhost:3000" in settings.cors_origins
    assert settings.nexus_env in ("development", "test", "production", "staging")
    assert settings.default_ai_provider == "openai"


def test_cors_origins_parsing():
    settings = NexusSettings(CORS_ORIGINS="http://localhost:3000, http://test.com")
    assert "http://localhost:3000" in settings.cors_origins
    assert "http://test.com" in settings.cors_origins
