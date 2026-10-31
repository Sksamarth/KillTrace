"""Local-file adaptation of the user's Mitigata SimEDR 1.0 generator.

Retains the supplied event families/weights and simulated alert metadata. Adds a
byte target, exclusive output, streaming SHA-256 and a manifest. Network sinks
are deliberately outside this local dataset task. Markdown links introduced by
chat formatting in BENIGN_DOMAINS are restored to their plain domain strings.
Seed fixes random choices, not UUIDs or wall-clock timestamps.
"""
import argparse
import hashlib
import json
import random
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

DOMAIN = "CORP"
VENDOR, PRODUCT, VERSION = "Mitigata", "SimEDR", "1.0"
HOSTS = [
    {"name": f"WS-{dept}-{i:03d}", "ip": f"10.10.{n}.{i}", "os": "windows", "os_ver": "Windows 11 Enterprise 23H2"}
    for n, dept in enumerate(["FIN", "HR", "ENG", "SALES"], start=1)
    for i in range(10, 16)
] + [
    {"name": "SRV-DC-01", "ip": "10.10.0.10", "os": "windows", "os_ver": "Windows Server 2022"},
    {"name": "SRV-FILE-01", "ip": "10.10.0.20", "os": "windows", "os_ver": "Windows Server 2022"},
    {"name": "SRV-WEB-01", "ip": "10.10.0.30", "os": "linux", "os_ver": "Ubuntu 22.04 LTS"},
    {"name": "SRV-DB-01", "ip": "10.10.0.40", "os": "linux", "os_ver": "RHEL 9.3"},
]
USERS = ["rkumar", "asharma", "pmehta", "sgupta", "nverma", "kiyer", "dnair", "vreddy", "jdsouza", "mkhan", "svc_backup", "svc_sql"]
WIN_PROCS = [
    ("chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe", "explorer.exe"),
    ("msedge.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "explorer.exe"),
    ("outlook.exe", r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE", "explorer.exe"),
    ("winword.exe", r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE", "explorer.exe"),
    ("excel.exe", r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE", "explorer.exe"),
    ("teams.exe", r"C:\Users\{u}\AppData\Local\Microsoft\Teams\current\Teams.exe", "explorer.exe"),
    ("svchost.exe", r"C:\Windows\System32\svchost.exe", "services.exe"),
    ("notepad.exe", r"C:\Windows\System32\notepad.exe", "explorer.exe"),
    ("OneDrive.exe", r"C:\Users\{u}\AppData\Local\Microsoft\OneDrive\OneDrive.exe", "explorer.exe"),
    ("MsMpEng.exe", r"C:\ProgramData\Microsoft\Windows Defender\Platform\4.18\MsMpEng.exe", "services.exe"),
]
LINUX_PROCS = [("sshd", "/usr/sbin/sshd", "systemd"), ("nginx", "/usr/sbin/nginx", "systemd"), ("cron", "/usr/sbin/cron", "systemd"), ("python3", "/usr/bin/python3", "bash"), ("postgres", "/usr/lib/postgresql/14/bin/postgres", "systemd")]
DOMAINS = ["login.microsoftonline.com", "outlook.office365.com", "www.google.com", "teams.microsoft.com", "github.com", "update.microsoft.com", "slack.com", "s3.amazonaws.com", "zoom.us"]
SUSPECT_DOMAINS = ["suspicious-example-c2.invalid", "bad-domain-demo.test", "sim-exfil.example"]
SUSPECT_IPS = ["198.51.100.23", "203.0.113.57", "192.0.2.88"]
SEVERITY = {"informational": 0, "low": 3, "medium": 5, "high": 8, "critical": 10}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def pid():
    return random.randint(1000, 65000)


def public_ip():
    return f"{random.choice([13, 20, 40, 52, 104, 142])}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def base_event(host, user, category, etype, action):
    return {
        "@timestamp": now_iso(),
        "event": {"id": str(uuid.uuid4()), "kind": "event", "category": [category], "type": [etype], "action": action, "severity": 0, "module": "edr", "dataset": f"edr.{category}"},
        "agent": {"id": hashlib.md5(host["name"].encode()).hexdigest()[:16], "type": "edr", "name": PRODUCT, "version": VERSION},
        "observer": {"vendor": VENDOR, "product": PRODUCT, "version": VERSION},
        "host": {"name": host["name"], "hostname": host["name"], "ip": [host["ip"]], "os": {"type": host["os"], "full": host["os_ver"]}},
        "user": {"name": user, "domain": DOMAIN},
    }


def proc_block(name, path, cmd, parent):
    return {"pid": pid(), "name": name, "executable": path, "command_line": cmd,
            "hash": {kind: getattr(hashlib, kind)(path.encode()).hexdigest() for kind in ("md5", "sha1", "sha256")},
            "parent": {"pid": pid(), "name": parent}, "entity_id": str(uuid.uuid4())}


def tag_alert(ev, tid, tname, tactic, rule_name, severity):
    ev["event"].update(kind="alert", severity=SEVERITY[severity])
    ev["threat"] = {"framework": "MITRE ATT&CK", "technique": {"id": [tid], "name": [tname]}, "tactic": {"name": [tactic]}}
    ev["rule"] = {"id": hashlib.md5(rule_name.encode()).hexdigest()[:8], "name": rule_name, "severity": severity}
    ev["labels"] = {"synthetic": "true", "simulated_detection": "true"}
    return ev


def benign_process(host, user):
    if host["os"] == "linux":
        name, path, parent = random.choice(LINUX_PROCS)
        cmd = f"{path} {random.choice(['', '-D', '--version'])}".strip()
    else:
        name, path, parent = random.choice(WIN_PROCS)
        path = path.format(u=user)
        cmd = f'"{path}"' + random.choice(["", " --type=renderer", " /safe", " -k netsvcs"])
    ev = base_event(host, user, "process", "start", "process_created")
    ev["process"] = proc_block(name, path, cmd, parent)
    return ev


def benign_network(host, user):
    ev = base_event(host, user, "network", "connection", "network_connection")
    ev["process"] = {"pid": pid(), "name": "chrome.exe" if host["os"] == "windows" else "curl"}
    ev["source"] = {"ip": host["ip"], "port": random.randint(49152, 65535)}
    ev["destination"] = {"ip": public_ip(), "port": random.choice([443, 443, 443, 80]), "domain": random.choice(DOMAINS)}
    ev["network"] = {"transport": "tcp", "direction": "outbound", "protocol": "https", "bytes": random.randint(500, 900000)}
    return ev


def benign_dns(host, user):
    ev = base_event(host, user, "network", "protocol", "dns_query")
    ev["dns"] = {"question": {"name": random.choice(DOMAINS), "type": "A"}, "response_code": "NOERROR", "resolved_ip": [public_ip()]}
    ev["process"] = {"pid": pid(), "name": "svchost.exe" if host["os"] == "windows" else "systemd-resolved"}
    return ev


def benign_file(host, user):
    if host["os"] == "windows":
        path = random.choice([rf"C:\Users\{user}\Documents\Q3_Report_{random.randint(1,9)}.xlsx", rf"C:\Users\{user}\Downloads\meeting_notes.docx", rf"C:\Users\{user}\AppData\Local\Temp\tmp{random.randint(1000,9999)}.tmp"])
        proc = random.choice(["excel.exe", "winword.exe", "explorer.exe"])
    else:
        path = random.choice(["/var/log/nginx/access.log", f"/home/{user}/app.py"])
        proc = random.choice(["nginx", "python3", "vim"])
    ev = base_event(host, user, "file", random.choice(["creation", "change"]), "file_modified")
    ev["file"] = {"path": path, "name": path.replace("\\", "/").split("/")[-1], "size": random.randint(100, 5_000_000)}
    ev["process"] = {"pid": pid(), "name": proc}
    return ev


def benign_auth(host, user):
    ev = base_event(host, user, "authentication", "start", "user_logon")
    ev["event"]["outcome"] = random.choices(["success", "failure"], [0.93, 0.07])[0]
    ev["winlog"] = {"event_id": 4624 if ev["event"]["outcome"] == "success" else 4625, "logon": {"type": random.choice(["Interactive", "Network", "RemoteInteractive"])}}
    ev["source"] = {"ip": random.choice(HOSTS)["ip"]}
    return ev


def benign_registry(host, user):
    if host["os"] != "windows":
        return benign_file(host, user)
    ev = base_event(host, user, "registry", "change", "registry_value_set")
    ev["registry"] = {"path": random.choice([r"HKCU\Software\Microsoft\Office\16.0\Common\General\RecentFiles", r"HKLM\SOFTWARE\Microsoft\Windows Defender\Signature Updates\AVSignatureVersion"]), "data": {"strings": [str(random.randint(1, 99999))]}}
    ev["process"] = {"pid": pid(), "name": random.choice(["chrome.exe", "MsMpEng.exe"])}
    return ev


def gen_benign():
    host, user = random.choice(HOSTS), random.choice(USERS)
    fn = random.choices([benign_process, benign_network, benign_dns, benign_file, benign_auth, benign_registry], [30, 25, 20, 12, 8, 5])[0]
    return fn(host, user)


def alert_suspicious_child():
    host = random.choice([h for h in HOSTS if h["name"].startswith("WS-")])
    user = random.choice(USERS[:10])
    ev = base_event(host, user, "process", "start", "process_created")
    ev["process"] = proc_block("powershell.exe", r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "powershell.exe -nop -w hidden -enc <REDACTED_BASE64>", "winword.exe")
    return tag_alert(ev, "T1059.001", "PowerShell", "Execution", "Office application spawned a scripting engine", "high")


def alert_c2_beacon():
    host = random.choice([h for h in HOSTS if h["name"].startswith("WS-")])
    user = random.choice(USERS[:10])
    ev = base_event(host, user, "network", "connection", "network_connection")
    ev["process"] = {"pid": pid(), "name": "powershell.exe"}
    ev["source"] = {"ip": host["ip"], "port": random.randint(49152, 65535)}
    ev["destination"] = {"ip": random.choice(SUSPECT_IPS), "port": 443, "domain": random.choice(SUSPECT_DOMAINS)}
    ev["network"] = {"transport": "tcp", "direction": "outbound", "bytes": random.randint(1000, 5000)}
    return tag_alert(ev, "T1071.001", "Web Protocols", "Command and Control", "Beaconing to low-reputation destination", "high")


def alert_bruteforce():
    host = next(h for h in HOSTS if h["name"] == "SRV-DC-01")
    user = random.choice(USERS)
    ev = base_event(host, user, "authentication", "start", "user_logon")
    ev["event"]["outcome"] = "failure"
    ev["winlog"] = {"event_id": 4625, "logon": {"type": "Network"}}
    ev["source"] = {"ip": random.choice(SUSPECT_IPS)}
    ev["labels_extra"] = {"failed_count_5min": random.randint(25, 120)}
    return tag_alert(ev, "T1110", "Brute Force", "Credential Access", "High rate of failed logons from single source", "medium")


def alert_persistence_runkey():
    host = random.choice([h for h in HOSTS if h["name"].startswith("WS-")])
    user = random.choice(USERS[:10])
    ev = base_event(host, user, "registry", "change", "registry_value_set")
    ev["registry"] = {"path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run\<SUSPECT_ENTRY>", "data": {"strings": [r"%AppData%\<redacted>.exe"]}}
    ev["process"] = {"pid": pid(), "name": "powershell.exe"}
    return tag_alert(ev, "T1547.001", "Registry Run Keys / Startup Folder", "Persistence", "Autorun key created by scripting engine", "high")


def alert_mass_file_change():
    host, user = random.choice(HOSTS), random.choice(USERS)
    ev = base_event(host, user, "file", "change", "file_rename")
    ev["file"] = {"path": rf"C:\Users\{user}\Documents\<many>.locked" if host["os"] == "windows" else f"/home/{user}/<many>.locked", "extension": "locked"}
    ev["labels_extra"] = {"files_renamed_60s": random.randint(200, 4000)}
    ev["process"] = {"pid": pid(), "name": "unknown.exe"}
    return tag_alert(ev, "T1486", "Data Encrypted for Impact", "Impact", "Rapid mass file rename to uniform extension", "critical")


ALERTS = [alert_suspicious_child, alert_c2_beacon, alert_bruteforce, alert_persistence_runkey, alert_mass_file_change]


def generate(path: Path, target_bytes: int, seed: int = 42, alert_ratio: float = 0.05):
    if target_bytes < 1 or not 0 <= alert_ratio <= 1:
        raise ValueError("positive byte target and alert ratio between zero and one required")
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() or manifest_path.exists():
        raise FileExistsError("Refusing to overwrite an existing dataset or manifest")
    if shutil.disk_usage(path.parent).free < target_bytes + 64 * 1024 * 1024:
        raise OSError("Insufficient disk space (target plus 64 MiB reserve required)")
    random.seed(seed)
    digest = hashlib.sha256()
    count = alerts = size = 0
    started = now_iso()
    next_progress = 128 * 1024 * 1024
    with partial.open("xb", buffering=1024 * 1024) as stream:
        while size < target_bytes:
            ev = random.choice(ALERTS)() if random.random() < alert_ratio else gen_benign()
            raw = (json.dumps(ev, separators=(",", ":")) + "\n").encode("utf-8")
            stream.write(raw)
            digest.update(raw)
            size += len(raw)
            count += 1
            alerts += ev["event"]["kind"] == "alert"
            if size >= next_progress:
                print(f"written {size:,} bytes / {count:,} records", flush=True)
                next_progress += 128 * 1024 * 1024
    partial.rename(path)
    manifest = {"generator_version": "simedr-local-1.0.0", "source": "user-supplied synthetic Mitigata SimEDR 1.0 generator", "synthetic": True, "file": path.name, "format": "jsonl", "encoding": "utf-8", "newline": "LF", "target_bytes": target_bytes, "actual_bytes": size, "records": count, "simulated_alerts": alerts, "seed": seed, "requested_alert_ratio": alert_ratio, "started_at": started, "completed_at": now_iso(), "sha256": digest.hexdigest(), "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    print(json.dumps(manifest, indent=2), flush=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/simedr-1gib.jsonl"))
    parser.add_argument("--target-bytes", type=int, default=1024**3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--alert-ratio", type=float, default=0.05)
    args = parser.parse_args()
    generate(args.output, args.target_bytes, args.seed, args.alert_ratio)
