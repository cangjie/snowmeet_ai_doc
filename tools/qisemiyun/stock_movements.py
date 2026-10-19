"""Export the inventory movement API for every product, with bounded concurrency."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sqlite3
import time

from client import Client, ROOT, redact

OUT = ROOT / "data"


def main():
    client = Client.load()
    products = [json.loads(line) for line in (OUT / "products_all.jsonl").read_text(encoding="utf-8").splitlines()]
    status_file = OUT / "status" / "stock_movements.json"
    cache_root = OUT / "pages" / "stock_movements"
    cache_root.mkdir(parents=True, exist_ok=True)
    def fetch(product):
        key = str(product["ProductId"])
        folder = cache_root / key
        folder.mkdir(exist_ok=True)
        all_rows, page, expected = [], 1, None
        while True:
            file = folder / f"{page:06d}.json"
            if file.exists():
                result = json.loads(file.read_text(encoding="utf-8"))
            else:
                result = None
                for attempt in range(2):
                    try:
                        result = client.post("/V1/User/Product/QueryProductIOList", {
                            "Page": page, "Rp": 1000, "SearchKey": "", "ProductId": key,
                            "StartDate": "", "EndDate": "", "WarehouseId": "", "ProductQueryType": "2",
                            "QueryBusiType": "0", "ChooseProductUnitName": "", "CSName": "", "BusiType": "",
                            "IsOtherWarehouseIO": "", "IsShowWriteBack": "1", "StartBusiDate": "",
                            "EndBusiDate": "", "LoginClientType": 1,
                            "QueryPageDataOnly": "0", "QueryPageTotalDataOnly": "0"})
                        break
                    except Exception as error:
                        if attempt:
                            return {"product_id": key, "state": "error", "error": str(error), "rows": all_rows}
                        time.sleep(1)
                time.sleep(.35)
                if result.get("IsSuccess"):
                    file.write_text(json.dumps(redact(result), ensure_ascii=False, indent=2), encoding="utf-8")
            if not result.get("IsSuccess"):
                return {"product_id": key, "state": "error", "error": result.get("Message"), "rows": all_rows}
            data = result.get("Data") or {}
            if expected is None:
                expected = int(data.get("Total") or 0)
            rows = data.get("List") or []
            all_rows.extend(redact(rows))
            if len(all_rows) >= expected or not rows:
                return {"product_id": key, "product_code": product.get("ProductCode"),
                        "state": "complete" if len(all_rows) == expected else "incomplete",
                        "expected": expected, "rows": all_rows, "pages": page}
            page += 1
    db = sqlite3.connect(OUT / "qisemiyun.sqlite3", timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    count, complete, nonempty, statuses = 0, 0, 0, []
    file = OUT / "stock_movements.jsonl"
    with file.open("w", encoding="utf-8", newline="\n") as stream:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for index, result in enumerate(pool.map(fetch, products), start=1):
                rows = result.pop("rows")
                if rows:
                    nonempty += 1
                complete += result["state"] == "complete"
                statuses.append(result | {"count": len(rows)})
                for position, row in enumerate(rows):
                    record = {"SourceProductId": result["product_id"], **row}
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                    key = result["product_id"] + ":" + str(position)
                    db.execute("INSERT OR REPLACE INTO records(module,record_id,data) VALUES(?,?,?)",
                               ("stock_movements", key, json.dumps(record, ensure_ascii=False)))
                    count += 1
                db.commit()
                if index % 100 == 0:
                    progress = {"module": "stock_movements", "label": "全部商品库存流水", "state": "running",
                                "products_processed": index, "products_total": len(products),
                                "products_complete": complete, "products_with_movements": nonempty, "count": count}
                    status_file.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(json.dumps(progress, ensure_ascii=False), flush=True)
    status = {"module": "stock_movements", "label": "全部商品库存流水",
              "state": "complete" if complete == len(products) else "incomplete", "count": count,
              "products_processed": len(products), "products_total": len(products), "products_complete": complete,
              "products_with_movements": nonempty, "products": statuses, "file": str(file),
              "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
              "scope": "Every exported product; all dates and warehouses; include voided documents as exposed by the API."}
    status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in status.items() if k != "products"}, ensure_ascii=False), flush=True)
    db.close()


if __name__ == "__main__":
    main()
