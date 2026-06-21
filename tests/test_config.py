from rtbdi_assistant.config import AssistantConfig


def test_config_from_env_reads_secret_names(monkeypatch):
    monkeypatch.setenv("RTBDI_BASE_URL", "https://example.test/newbdi/index.fwx")
    monkeypatch.setenv("RTBDI_USERNAME", "user")
    monkeypatch.setenv("RTBDI_PASSWORD", "pass")
    monkeypatch.setenv("OPENAI_API_KEY", "key")

    config = AssistantConfig.from_env()

    assert config.rtbdi_base_url == "https://example.test/newbdi/index.fwx"
    assert config.require_rtbdi_credentials() == ("user", "pass")
    assert config.require_openai_key() == "key"
