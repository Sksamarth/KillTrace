from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KILLCHAIN_", extra="ignore")

    data_dir: Path = Path("data")
    duckdb_memory_limit: str = Field(default="1GB", pattern=r"^[1-9][0-9]*(MB|GB)$")
    duckdb_threads: int = Field(default=2, ge=1, le=4)
    duckdb_max_temp_size: str = Field(default="10GB", pattern=r"^[1-9][0-9]*(MB|GB)$")
