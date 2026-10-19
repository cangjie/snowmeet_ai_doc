"""Category hierarchy and stocktake document details."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sqlite3
import time

from client import Client, ROOT, redact

OUT = ROOT / "data"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    client = Client.load()
    db = sqlite3.connect(OUT / "qisemiyun.sqlite3", timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    categories = [json.loads(line) for line in (OUT / "product_classes.jsonl").read_text(encoding="utf-8").splitlines()]
    seen = {str(row["ClassId"]).lower() for row in categories}
    queue = [row for row in categories if int(row.get("ChildCount") or 0) > 0]
    errors = []
    def fetch_children(parent):
        key = str(parent["ClassId"])
        path = OUT / "pages" / "product_classes_tree" / (key + ".json")
        if path.exists():
            result = json.loads(path.read_text(encoding="utf-8"))
        else:
            result = client.post("/V1/User/ProductClass/QueryProductClassList", {
                "Page": 1, "Rp": 10000, "ClassType": "1", "ParentClassId": key, "LoginClientType": 1})
            if result.get("IsSuccess"):
                save(path, redact(result))
            time.sleep(.4)
        return parent, result
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        while queue:
            following = []
            for parent, result in pool.map(fetch_children, queue):
                if not result.get("IsSuccess"):
                    errors.append({"ClassId": parent["ClassId"], "message": result.get("Message")})
                    continue
                children = result.get("Data") or []
                for row in children:
                    key = str(row["ClassId"]).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    categories.append(row)
                    if int(row.get("ChildCount") or 0) > 0:
                        following.append(row)
            queue = following
            print(json.dumps({"stage": "category_tree", "count": len(categories), "parents_left": len(queue)}), flush=True)
    referenced = {str(json.loads(line).get("ClassId")).lower() for line in (OUT / "products_all.jsonl").read_text(encoding="utf-8").splitlines()}
    missing = sorted(referenced - seen)
    target = OUT / "product_classes_tree.jsonl"
    jsonl(target, categories)
    for row in categories:
        db.execute("INSERT OR REPLACE INTO records(module,record_id,data) VALUES(?,?,?)",
                   ("product_classes_tree", str(row["ClassId"]), json.dumps(row, ensure_ascii=False)))
    db.commit()
    save(OUT / "status" / "product_classes_tree.json", {"module": "product_classes_tree", "label": "完整商品分类层级",
         "state": "complete" if not errors and not missing else "incomplete", "count": len(categories),
         "errors": errors, "missing_referenced_class_ids": missing, "file": str(target)})
    documents = [json.loads(line) for line in (OUT / "stocktaking.jsonl").read_text(encoding="utf-8").splitlines()]
    def fetch_stocktake(row):
        key = str(row["TakBillId"])
        file = OUT / "pages" / "stocktaking_details" / (key + ".json")
        if file.exists():
            result = json.loads(file.read_text(encoding="utf-8"))
        else:
            result = client.post("/V1/User/StoreReserve/QueryTakByBillIdNoProduct", {"TakBillId": key, "LoginClientType": 1})
            if result.get("IsSuccess"):
                save(file, redact(result))
            time.sleep(.4)
        return row, result
    details, lines, failures = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for index, (source, result) in enumerate(pool.map(fetch_stocktake, documents), start=1):
            key = str(source["TakBillId"])
            if not result.get("IsSuccess"):
                failures.append({"id": key, "message": result.get("Message")})
                continue
            data = redact(result.get("Data") or {})
            details.append(data)
            db.execute("INSERT OR REPLACE INTO records(module,record_id,data) VALUES(?,?,?)",
                       ("stocktaking_details", key, json.dumps(data, ensure_ascii=False)))
            for position, row in enumerate(data.get("BillDetails") or []):
                value = {"SourceTakBillId": key, "SourceTakBillNo": source.get("TakBillNo"), **row}
                lines.append(value)
                db.execute("INSERT OR REPLACE INTO records(module,record_id,data) VALUES(?,?,?)",
                           ("stocktaking_lines", key + ":" + str(position), json.dumps(value, ensure_ascii=False)))
            db.commit()
            if index % 20 == 0:
                print(json.dumps({"stage": "stocktake_details", "documents": index, "total": len(documents), "lines": len(lines)}), flush=True)
    jsonl(OUT / "stocktaking_details.jsonl", details)
    jsonl(OUT / "stocktaking_lines.jsonl", lines)
    save(OUT / "status" / "stocktaking_details.json", {"module": "stocktaking_details", "label": "盘点单完整详情",
         "state": "complete" if not failures and len(details) == len(documents) else "incomplete",
         "count": len(details), "expected": len(documents), "line_count": len(lines), "errors": failures,
         "file": str(OUT / "stocktaking_details.jsonl")})
    save(OUT / "status" / "stocktaking_lines.json", {"module": "stocktaking_lines", "label": "盘点商品明细",
         "state": "complete" if not failures else "incomplete", "count": len(lines),
         "file": str(OUT / "stocktaking_lines.jsonl")})
    print(json.dumps({"category_count": len(categories), "missing_categories": len(missing), "stocktaking_documents": len(details),
                      "stocktaking_lines": len(lines), "errors": len(failures)}, ensure_ascii=False), flush=True)
    db.close()


if __name__ == "__main__":
    main()
