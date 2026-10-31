import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app
from app.storage import open_database


def test_health_contract():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "KillChain AI", "version": "0.1.0"}
        assert client.get("/api/incidents").status_code == 404


def test_disk_storage_configuration_and_persistence(tmp_path):
    settings = Settings(data_dir=tmp_path, duckdb_memory_limit="128MB", duckdb_threads=1)
    with open_database(settings) as db:
        assert db.execute("SELECT current_setting('threads')").fetchone()[0] == 1
        assert db.execute("SELECT current_setting('enable_external_access')").fetchone()[0] is False
        db.execute("CREATE TABLE foundation_check (value INTEGER)")
        db.execute("INSERT INTO foundation_check VALUES (42)")
    with open_database(settings) as db:
        assert db.execute("SELECT value FROM foundation_check").fetchone()[0] == 42
    assert (tmp_path / "killchain.duckdb").is_file()


def test_invalid_resource_configuration():
    with pytest.raises(ValidationError):
        Settings(duckdb_threads=0)
    with pytest.raises(ValidationError):
        Settings(duckdb_memory_limit="unlimited")
