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

    # Target VM (separate Ubuntu Server box where sshd lives and where iptables blocks land)
    target_host: str = "192.168.56.12"
    target_user: str = "siem"
    target_ssh_key: str = "~/.ssh/siem_orchestrator_ed25519"
    target_ssh_timeout: int = 10


settings = Settings()
