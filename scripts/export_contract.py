"""Rebuild checked-in schema artifacts from the Python source of truth."""
import json
from pathlib import Path

from app.contracts.arrow_v1 import ARROW_SCHEMA
from app.contracts.v1 import CanonicalEvent, RecordValidation


def export(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    for name, model in (("event.schema.json", CanonicalEvent), ("validation.schema.json", RecordValidation)):
        (directory / name).write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
    (directory / "arrow-schema.txt").write_text(str(ARROW_SCHEMA) + "\n", encoding="utf-8")


if __name__ == "__main__":
    export(Path(__file__).resolve().parents[1] / "schemas" / "v1")
