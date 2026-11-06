from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from file_cleaner.domain.rules import CleanupRule, RulePolicy, validate_attach_grace

HOUR = 3600


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    file_service_url: str = "http://localhost:8001"
    internal_api_key: str = "dev-internal-api-key-change-me"
    request_timeout_seconds: float = 30
    batch_limit: int = 100

    upload_session_ttl_seconds: int = 24 * HOUR
    stale_active_interval_seconds: int = 15 * 60
    assembly_stuck_ttl_seconds: int = 1 * HOUR
    stuck_assembling_interval_seconds: int = 15 * 60
    attach_grace_period_seconds: int = 48 * HOUR
    unattached_interval_seconds: int = 1 * HOUR
    terminal_purge_delay_seconds: int = 10 * 60
    terminal_interval_seconds: int = 15 * 60
    orphan_chunk_dir_min_age_seconds: int = 1 * HOUR
    orphan_chunk_dirs_interval_seconds: int = 1 * HOUR
    backend_upload_event_max_age_seconds: int = 6 * HOUR

    def policies(self) -> list[RulePolicy]:
        validate_attach_grace(
            self.attach_grace_period_seconds, self.backend_upload_event_max_age_seconds
        )
        return [
            RulePolicy(
                CleanupRule.STALE_ACTIVE,
                self.upload_session_ttl_seconds,
                self.stale_active_interval_seconds,
            ),
            RulePolicy(
                CleanupRule.STUCK_ASSEMBLING,
                self.assembly_stuck_ttl_seconds,
                self.stuck_assembling_interval_seconds,
            ),
            RulePolicy(
                CleanupRule.UNATTACHED,
                self.attach_grace_period_seconds,
                self.unattached_interval_seconds,
            ),
            RulePolicy(
                CleanupRule.TERMINAL,
                self.terminal_purge_delay_seconds,
                self.terminal_interval_seconds,
            ),
            RulePolicy(
                CleanupRule.ORPHAN_CHUNK_DIRS,
                self.orphan_chunk_dir_min_age_seconds,
                self.orphan_chunk_dirs_interval_seconds,
            ),
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
