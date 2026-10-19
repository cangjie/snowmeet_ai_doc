"""Resumable, sequential export of explicitly selected read-only list APIs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from client import Client, ROOT, redact

CST = timezone(timedelta(hours=8))
EXPORT = ROOT / "data"


def now():
    return datetime.now(CST).isoformat(timespec="seconds")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def unpack(result, module=None):
    data = result.get("Data")
    if isinstance(data, dict):
        keys = [module["rows_key"]] if module and module.get("rows_key") else ["List", "Rows", "list", "rows"]
        for key in keys:
            if isinstance(data.get(key), list):
                return data[key], data.get("Total", data.get("TotalCount"))
    if isinstance(data, list):
        return data, None
    if isinstance(result.get("List"), list):
        return result["List"], result.get("Total")
    if isinstance(data, dict):
        return [data], None
    return [], None


def export(client, module, db):
    name = module["name"]
    folder = EXPORT / "pages" / name
    folder.mkdir(parents=True, exist_ok=True)
    status_path = EXPORT / "status" / (name + ".json")
    request_context = {"path": module["path"], "payload": module.get("payload", {})}
    context_path = folder / "_request.json"
    if not context_path.exists() and status_path.exists():
        old_status = json.loads(status_path.read_text(encoding="utf-8"))
        save(context_path, {"path": old_status.get("path"), "payload": old_status.get("payload", {})})
    if context_path.exists() and json.loads(context_path.read_text(encoding="utf-8")) != request_context:
        fingerprint = hashlib.sha256(json.dumps(request_context, sort_keys=True).encode()).hexdigest()[:12]
        folder = folder / fingerprint
        folder.mkdir(exist_ok=True)
    else:
        save(context_path, request_context)
    status = {"module": name, "label": module["label"], "path": module["path"],
              "payload": module.get("payload", {}), "started_at": now(), "state": "running"}
    save(status_path, status)
    page, expected, records, duplicate_ids = 1, None, [], []
    seen = set()
    output = EXPORT / (name + ".jsonl")
    while True:
        payload = {"LoginClientType": 1, "AppId": 1, "VersionCode": 54,
                   "Page": page, "Rp": 100, "QueryPageDataOnly": "0", "QueryPageTotalDataOnly": "0",
                   **module.get("payload", {})}
        cache = folder / f"{page:06d}.json"
        if cache.exists():
            result = json.loads(cache.read_text(encoding="utf-8"))
        else:
            result = client.post(module["path"], payload)
            time.sleep(.65)
            if not result.get("IsSuccess"):
                status.update(state="failed", page=page, message=result.get("Message"),
                              request_state=result.get("RequestState"), finished_at=now())
                save(status_path, status)
                print(json.dumps(status, ensure_ascii=False), flush=True)
                return
            save(cache, redact(result))
        rows, total = unpack(result, module)
        if page == 1:
            expected = int(total) if total is not None else None
            status["expected"] = expected
        elif total is not None and expected != int(total):
            status.setdefault("total_changes", []).append({"page": page, "total": total})
        new_count = 0
        for row in rows:
            row = redact(row)
            key = row.get(module.get("id_field", "")) if isinstance(row, dict) else None
            if key is None:
                key = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            key = str(key)
            if key in seen:
                duplicate_ids.append(key)
                continue
            seen.add(key)
            new_count += 1
            records.append(row)
            db.execute("INSERT OR REPLACE INTO records(module, record_id, data) VALUES (?, ?, ?)",
                       (name, key, json.dumps(row, ensure_ascii=False)))
        db.commit()
        status.update(last_page=page, collected=len(records), duplicates=len(duplicate_ids), updated_at=now())
        save(status_path, status)
        if page % 10 == 0:
            print(json.dumps({"module": name, "page": page, "collected": len(records),
                              "expected": expected}, ensure_ascii=False), flush=True)
        if module.get("single") or not rows:
            break
        if expected is not None and len(records) >= expected:
            break
        if new_count == 0:
            status["warning"] = "Repeated page; API may not support the selected pagination"
            break
        if expected is None and len(rows) < 100:
            break
        page += 1
        if page > 10000:
            status["warning"] = "Page limit reached"
            break
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    dates = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            if (key.endswith("Date") or key.endswith("DateStr")) and isinstance(value, str) and len(value) >= 10:
                if value[:4].isdigit() and value[4:5] == "-":
                    old = dates.setdefault(key, {"min": value[:10], "max": value[:10]})
                    old["min"] = min(old["min"], value[:10])
                    old["max"] = max(old["max"], value[:10])
    complete = (expected is None or len(records) == expected) and not status.get("warning") and not status.get("total_changes")
    status.update(state="complete" if complete else "incomplete", count=len(records), date_ranges=dates,
                  file=str(output), sha256=hashlib.sha256(output.read_bytes()).hexdigest(), finished_at=now())
    save(status_path, status)
    print(json.dumps(status, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    modules = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.only:
        modules = [m for m in modules if m["name"] in args.only]
    EXPORT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(EXPORT / "qisemiyun.sqlite3", timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("CREATE TABLE IF NOT EXISTS records (module TEXT NOT NULL, record_id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(module, record_id))")
    client = Client.load()
    for module in modules:
        tail = module["path"].rstrip("/").rsplit("/", 1)[-1]
        known_read_reports = {"/V1/User/InventoryReport/Inventory"}
        if not tail.lower().startswith(("query", "get", "list", "search")) and module["path"] not in known_read_reports:
            raise ValueError("Read-only list endpoint required: " + module["path"])
        try:
            export(client, module, db)
        except Exception as error:
            status = {"module": module["name"], "state": "error", "error": str(error), "finished_at": now()}
            save(EXPORT / "status" / (module["name"] + ".json"), status)
            print(json.dumps(status, ensure_ascii=False), flush=True)
    db.close()


if __name__ == "__main__":
    main()
