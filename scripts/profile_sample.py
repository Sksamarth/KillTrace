"""Bounded JSONL inspection, not an ingestion engine. Reports stay under data/.

Maximum physical record: 1 MiB. At most 512 field paths and 128 categorical
values per counter. Exact byte-record and source-event-ID duplicate checks use
a disposable SQLite index on disk (8 MiB page cache), not Python sets.
"""
import argparse
import hashlib
import ipaddress
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

MAX_RECORD_BYTES = 1024 * 1024


def profile(path: Path, report_path: Path):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    index_path = report_path.with_suffix(".sqlite")
    # Exclusive temporary index avoids damaging any existing data.
    with index_path.open("xb"):
        pass
    db = sqlite3.connect(index_path)
    db.execute("PRAGMA cache_size=-8192")
    db.execute("PRAGMA temp_store=FILE")
    db.execute("CREATE TABLE hashes (kind TEXT, value TEXT, PRIMARY KEY(kind,value)) WITHOUT ROWID")
    counts = Counter()
    paths = defaultdict(Counter)
    values = defaultdict(Counter)
    minimum = maximum = None
    digest = hashlib.sha256()

    def add_value(name, value):
        key = str(value)
        # Reserve one of the 128 slots for the overflow bucket.
        if key not in values[name] and len(values[name]) >= 127:
            key = "<other: cardinality capped>"
        values[name][key] += 1

    def walk(obj, prefix=""):
        for key, value in obj.items():
            name = f"{prefix}.{key}" if prefix else key
            if name not in paths and len(paths) >= 512:
                raise ValueError("field inventory exceeds 512 paths")
            stat = paths[name]
            stat["present_records"] += 1
            stat[type(value).__name__] += 1
            if value is None:
                stat["null"] += 1
            if value == "" or value == [] or value == {}:
                stat["empty"] += 1
            if isinstance(value, dict):
                walk(value, name)

    def unique(kind, value):
        cursor = db.execute("INSERT OR IGNORE INTO hashes VALUES (?, ?)", (kind, value))
        counts[f"duplicate_{kind}"] += cursor.rowcount == 0

    try:
        with path.open("rb") as stream:
            while raw := stream.readline(MAX_RECORD_BYTES + 1):
                if len(raw) > MAX_RECORD_BYTES:
                    raise ValueError("record exceeds 1 MiB inspection bound")
                counts["physical_lines"] += 1
                counts["bytes"] += len(raw)
                counts["max_record_bytes"] = max(counts["max_record_bytes"], len(raw))
                digest.update(raw)
                counts["crlf_records"] += raw.endswith(b"\r\n")
                counts["lf_records"] += raw.endswith(b"\n") and not raw.endswith(b"\r\n")
                try:
                    text = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    counts["invalid_utf8"] += 1
                    continue
                counts["bom_records"] += text.startswith("\ufeff")
                unique("raw_records", hashlib.sha256(raw).hexdigest())
                try:
                    ev = json.loads(text)
                    if not isinstance(ev, dict):
                        raise ValueError("not an object")
                except (ValueError, RecursionError):
                    counts["malformed_records"] += 1
                    continue
                counts["valid_json_objects"] += 1
                walk(ev)
                event = ev.get("event", {})
                if event.get("id") is not None:
                    unique("event_ids", str(event["id"]))
                for key in ("kind", "action", "severity", "outcome"):
                    if key in event:
                        add_value(f"event.{key}", event[key])
                for key in ("category", "type"):
                    for val in event.get(key, []):
                        add_value(f"event.{key}", val)
                add_value("host.name", ev.get("host", {}).get("name"))
                add_value("host.os.type", ev.get("host", {}).get("os", {}).get("type"))
                add_value("user.name", ev.get("user", {}).get("name"))
                timestamp = ev.get("@timestamp")
                if timestamp is None:
                    counts["missing_timestamp"] += 1
                else:
                    try:
                        instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        if instant.tzinfo is None:
                            counts["offset_unknown"] += 1
                        else:
                            counts["offset_known"] += 1
                            minimum = min(minimum, instant) if minimum else instant
                            maximum = max(maximum, instant) if maximum else instant
                        counts["utc_millisecond_z"] += bool(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", timestamp))
                    except (ValueError, TypeError, AttributeError):
                        counts["invalid_timestamp"] += 1
                ips = list(ev.get("host", {}).get("ip", []))
                ips += [obj["ip"] for obj in (ev.get("source", {}), ev.get("destination", {})) if "ip" in obj]
                ips += ev.get("dns", {}).get("resolved_ip", [])
                for ip in ips:
                    try:
                        counts[f"valid_ipv{ipaddress.ip_address(ip).version}_values"] += 1
                    except ValueError:
                        counts["invalid_ip_values"] += 1
                if counts["physical_lines"] % 10000 == 0:
                    db.commit()
                if counts["physical_lines"] % 250000 == 0:
                    print(f"profiled {counts['physical_lines']:,} records", flush=True)
        db.commit()
        result = {
            "file": path.name, "sha256": digest.hexdigest(), "counts": dict(counts),
            "timestamp_min": minimum.isoformat() if minimum else None,
            "timestamp_max": maximum.isoformat() if maximum else None,
            "fields": {key: {**dict(stat), "missing_records": counts["valid_json_objects"] - stat["present_records"]} for key, stat in sorted(paths.items())},
            "vocabularies": {key: dict(value) for key, value in values.items()},
            "synthetic": True,
        }
        with report_path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        # Only the exact temporary index created above is removed after success.
        db.close()
        index_path.unlink()
        print(json.dumps({k: v for k, v in result.items() if k not in ("fields", "vocabularies")}, indent=2), flush=True)
        return result
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    profile(args.path, args.report)
