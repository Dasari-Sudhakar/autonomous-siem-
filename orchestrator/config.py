from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    es_url: str = "http://localhost:9200"
    es_index: str = "filebeat-*"
    alerts_index: str = "siem-alerts"
    response_index: str = "siem-response"

    rule_window_seconds: int = 60
    rule_threshold: int = 5
    block_ttl_seconds: int = 3600
    poll_interval_seconds: int = 10

    sqlite_path: str = "/var/lib/siem/responses.db"
    model_path: str = "ml/isolation_forest.pkl"

    enable_responder: bool = True
    dry_run: bool = False


settings = Settings()
