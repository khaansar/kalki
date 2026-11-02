from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="KALKI_", extra="ignore")

    enabled: bool = False
    allowed_user_ids: Annotated[frozenset[str], NoDecode] = frozenset()

    cooldown_minutes: int = Field(default=30, ge=0)
    skip_extra_wait_minutes: int = Field(default=30, ge=0)
    max_wait_minutes: int = Field(default=720, ge=0)
    prompt_ttl_minutes: int = Field(default=10, ge=1)
    sleep_options_minutes: Annotated[list[int], NoDecode] = [30, 60, 240, 1440]
    seen_window_days: int = Field(default=30, ge=0)

    openai_model: str = "gpt-4o-mini"
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_timeout_seconds: float = Field(default=60, gt=0)
    openai_input_usd_per_million: float = Field(default=0.15, ge=0)
    openai_output_usd_per_million: float = Field(default=0.60, ge=0)
    daily_spend_limit_usd: float = Field(default=2.0, gt=0)

    rewrite_max_retries: int = Field(default=1, ge=0)
    job_max_attempts: int = Field(default=3, ge=1)
    job_retry_delay_minutes: int = Field(default=15, ge=0)
    worker_poll_seconds: float = Field(default=10, gt=0)
    free_tests_run_hour_utc: int = Field(default=2, ge=0, le=23)

    test_service_url: str = Field(validation_alias="TEST_SERVICE_URL")
    attempt_service_url: str = Field(validation_alias="ATTEMPT_SERVICE_URL")
    payment_service_url: str = Field(validation_alias="PAYMENT_SERVICE_URL")
    service_secret: SecretStr = Field(min_length=1)
    gateway_secret: SecretStr = Field(min_length=1, validation_alias="API_GATEWAY_SECRET")
    live_request_timeout_seconds: float = Field(default=2, gt=0)
    blueprint_timeout_seconds: float = Field(default=30, gt=0)

    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic: str = "attempt-submitted-events"
    kafka_group_id: str = "kalki-worker"

    mysql_host: str = Field(default="localhost", validation_alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    mysql_database: str = "kalki"
    mysql_user: str = "kalki"
    mysql_password: SecretStr = Field(min_length=1)
    mysql_tls_enabled: bool = True
    mysql_tls_ca_path: str | None = None

    @field_validator("allowed_user_ids", "sleep_options_minutes", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def check_values(self) -> "Settings":
        if not self.sleep_options_minutes or min(self.sleep_options_minutes) <= 0:
            raise ValueError("KALKI_SLEEP_OPTIONS_MINUTES must be positive numbers")
        if self.max_wait_minutes < self.cooldown_minutes:
            raise ValueError("KALKI_MAX_WAIT_MINUTES must not be below KALKI_COOLDOWN_MINUTES")
        return self

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
