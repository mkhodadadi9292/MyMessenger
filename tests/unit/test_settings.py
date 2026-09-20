from app.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_name == "Messenger"
    assert settings.access_token_ttl_minutes == 30
    assert settings.refresh_token_ttl_days == 30
    assert settings.otp_ttl_seconds == 300
    assert settings.otp_length == 6
    assert settings.max_artifact_size_mb == 20


def test_settings_override() -> None:
    settings = Settings(otp_ttl_seconds=60, jwt_secret="x", _env_file=None)
    assert settings.otp_ttl_seconds == 60
    assert settings.jwt_secret == "x"
