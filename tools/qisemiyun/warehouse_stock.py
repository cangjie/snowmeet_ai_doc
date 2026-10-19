"""Export nonzero stock by warehouse and reconcile it to the overall stock."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections import defaultdict
from decimal import Decimal

from client import Client, ROOT, redact

OUT = ROOT / "data"


def main():
    client = Client.load()
    warehouses = [json.loads(line) for line in (OUT / "warehouses.jsonl").read_text(encoding="utf-8").splitlines()]
    all_stock = {str(row["productid"]).lower(): row for row in
                 (json.loads(line) for line in (OUT / "stock.jsonl").read_text(encoding="utf-8").splitlines())}
    totals = defaultdict(Decimal)
    rows_all, results = [], []
    db = sqlite3.connect(OUT / "qisemiyun.sqlite3", timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    for index, warehouse in enumerate(warehouses, start=1):
        warehouse_id = warehouse["WarehouseId"]
        page, total, count = 1, None, 0
        while True:
            folder = OUT / "pages" / "stock_by_warehouse" / warehouse_id
            folder.mkdir(parents=True, exist_ok=True)
            file = folder / f"{page:06d}.json"
            if file.exists():
                result = json.loads(file.read_text(encoding="utf-8"))
            else:
                result = client.post("/V1/User/InventoryReport/Inventory", {
                    "Page": page, "Rp": 1000, "QueryType": "0", "SearchType": 1,
                    "SearchKey": "", "ClassId": "", "WarehouseId": warehouse_id,
                    "StartDate": "", "EndDate": "", "UserId": client.session["UserId"],
                    "OpenSOBDate": "null", "ProductQueryType": "2", "IsShowZero": "",
                    "IsShowStop": "1", "IsQueryTopData": 0, "PositionId": "",
                    "LoginClientType": 1, "QueryPageDataOnly": "0", "QueryPageTotalDataOnly": "0"})
                if result.get("IsSuccess"):
                    file.write_text(json.dumps(redact(result), ensure_ascii=False, indent=2), encoding="utf-8")
                time.sleep(.6)
            if not result.get("IsSuccess"):
                results.append({"warehouse_id": warehouse_id, "state": "error", "message": result.get("Message")})
                break
            data = result.get("Data") or {}
            rows = data.get("ProductList") or []
            if total is None:
                total = int(data.get("TotalCount") or 0)
            for source in rows:
                row = {"WarehouseId": warehouse_id, "WarehouseName": warehouse["WarehouseName"], **source}
                rows_all.append(row)
                product_id = str(row["productid"]).lower()
                totals[product_id] += Decimal(str(row.get("currentstockcount") or 0))
                key = warehouse_id.lower() + ":" + product_id
                db.execute("INSERT OR REPLACE INTO records(module,record_id,data) VALUES (?,?,?)",
                           ("stock_by_warehouse", key, json.dumps(row, ensure_ascii=False)))
            db.commit()
            count += len(rows)
            if count >= total or not rows:
                results.append({"warehouse_id": warehouse_id, "name": warehouse["WarehouseName"],
                                "state": "complete" if count == total else "incomplete", "rows": count, "expected": total})
                break
            page += 1
        if index % 10 == 0:
            print(json.dumps({"warehouses": index, "total": len(warehouses), "rows": len(rows_all)}), flush=True)
    output = OUT / "stock_by_warehouse.jsonl"
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows_all:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    differences = []
    for key, source in all_stock.items():
        expected = Decimal(str(source.get("currentstockcount") or 0))
        if abs(expected - totals[key]) > Decimal("0.000001"):
            differences.append({"product_id": source["productid"], "aggregate": str(expected), "warehouse_sum": str(totals[key])})
    status = {"module": "stock_by_warehouse", "label": "各仓库非零库存", "warehouses": len(warehouses),
              "count": len(rows_all), "state": "complete" if all(r["state"] == "complete" for r in results) and not differences else "incomplete",
              "warehouses_result": results, "reconciliation_differences": differences,
              "file": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "scope": "All listed warehouses; zero physical balances omitted; zeroes are represented by product and warehouse masters."}
    (OUT / "status" / "stock_by_warehouse.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in status.items() if k not in ("warehouses_result", "reconciliation_differences")} | {
        "differences": len(differences)}, ensure_ascii=False), flush=True)
    db.close()


if __name__ == "__main__":
    main()
