from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KILLCHAIN_", extra="ignore", env_ignore_empty=True)

    data_dir: Path = Path("data")
    duckdb_memory_limit: str = Field(default="1GB", pattern=r"^[1-9][0-9]*(MB|GB)$")
    duckdb_threads: int = Field(default=2, ge=1, le=4)
    duckdb_max_temp_size: str = Field(default="10GB", pattern=r"^[1-9][0-9]*(MB|GB)$")
    ingestion_input_dir: Path | None = None
    ingestion_batch_rows: int = Field(default=4096, ge=1, le=65536)
    ingestion_batch_bytes: int = Field(default=8 * 1024**2, ge=1024, le=64 * 1024**2)
    ingestion_row_group_rows: int = Field(default=1024, ge=1, le=65536)
    ingestion_memory_mb: int = Field(default=768, ge=128, le=4096)
    ingestion_temp_bytes: int = Field(default=64 * 1024**2, ge=3 * 1024**2, le=1024**3)
    ingestion_disk_reserve_bytes: int = Field(default=256 * 1024**2, ge=0)

    @model_validator(mode="after")
    def bounded_ingestion(self):
        if self.ingestion_row_group_rows > self.ingestion_batch_rows:
            # A row group cannot exceed its containing bounded batch.
            self.ingestion_row_group_rows = self.ingestion_batch_rows
        if self.ingestion_temp_bytes < self.ingestion_batch_bytes + 2 * 1024**2:
            raise ValueError("temporary budget needs batch payload plus 2 MiB reserve")
        if self.ingestion_batch_bytes > self.ingestion_memory_mb * 1024**2 // 4:
            raise ValueError("batch payload must be at most one quarter of memory admission budget")
        return self
