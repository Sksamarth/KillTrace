"""Disk-backed connection factory for a future single processing worker.

The API does not open the database. Do not share a writable database between
independent API/worker processes. No dataset schema is created here.
"""
import duckdb

from app.config import Settings


def open_database(settings: Settings) -> duckdb.DuckDBPyConnection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    spill = settings.data_dir / "spill"
    spill.mkdir(exist_ok=True)
    connection = duckdb.connect(
        str(settings.data_dir / "killchain.duckdb"),
        config={
            "memory_limit": settings.duckdb_memory_limit,
            "threads": settings.duckdb_threads,
            "temp_directory": str(spill),
            "max_temp_directory_size": settings.duckdb_max_temp_size,
            "preserve_insertion_order": False,
        },
    )
    # Apply this after spill configuration: DuckDB otherwise rejects configuring
    # temp_directory when external access is disabled during connection startup.
    try:
        connection.execute("SET enable_external_access = false")
    except Exception:
        connection.close()
        raise
    return connection
