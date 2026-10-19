"""Save document attachments and product images with source-to-file mappings."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import mimetypes
import sqlite3
import time
import urllib.parse
from pathlib import Path
from platform_support import http_connection

from client import Client, ROOT, SOURCE_IP, redact

OUT = ROOT / "data"
MEDIA = OUT / "media"


def load_rows(name):
    file = OUT / (name + ".jsonl")
    values = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()] if file.exists() else []
    return [{**value['Data'],'SourceId':value.get('SourceId')} if isinstance(value.get('Data'),dict) and 'SourceId' in value else value for value in values]


def document_attachments():
    folder = MEDIA / "attachment_metadata"
    folder.mkdir(parents=True, exist_ok=True)
    specs = [("sales", "SaleId", "3"), ("sales_history_details", "SaleId", "3"), ("purchases", "BuyId", "1"), ("purchases_history_details", "BuyId", "1"),
             ("sales_returns", "ReturnId", "4"), ("purchase_returns", "ReturnId", "2"),
             ("transfers", "TranId", "7"), ("receipts", "ReceiveId", "14"),
             ("payments", "PaymentId", "15"), ("stocktaking", "TakBillId", "5")]
    work = []
    for module, id_field, kind in specs:
        for row in load_rows(module):
            if row.get("BusiFileCount") or row.get("BusiFileList"):
                work.append((module, id_field, kind, row))
    def fetch(item):
        module, id_field, kind, row = item
        key = str(row[id_field])
        target = folder / (module + "." + key + ".json")
        expected = int(row.get("BusiFileCount") or len(row.get("BusiFileList") or []))
        data = None
        if target.exists():
            data = json.loads(target.read_text(encoding="utf-8"))
            if len(data) != expected or any(str(x.get("BusiType")) != kind for x in data if x.get("BusiType") is not None):
                data = None
        if data is None:
            client = Client.load()
            result = client.post("/V1/User/Common/QueryBusiAttachmentList", {
                "BusiId": key, "BusiType": kind, "LoginClientType": 1})
            if not result.get("IsSuccess"):
                return {"module": module, "id": key, "error": result.get("Message")}
            data = redact(result.get("Data") or [])
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(.3)
        return {"module": module, "id": key, "files": data, "expected": expected,
                "count_matches": len(data) == expected}
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for index, result in enumerate(pool.map(fetch, work), start=1):
            results.append(result)
            if index % 50 == 0:
                print(json.dumps({"stage": "attachments", "documents": index, "total": len(work)}), flush=True)
    (MEDIA / "documents.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def file_tasks(documents):
    tasks = []
    for row in load_rows("products_all"):
        product_id = row.get("ProductId")
        for image in row.get("ProductImgList") or []:
            if isinstance(image, dict) and image.get("ImageUrl"):
                tasks.append({"category": "product_image", "module": "products_all", "id": product_id,
                              "url": image["ImageUrl"], "name": str(image.get("Id", ""))})
        if row.get("ProductImg"):
            tasks.append({"category": "product_image", "module": "products_all", "id": product_id,
                          "url": row["ProductImg"], "name": "main"})
    for doc in documents:
        for file in doc.get("files", []):
            if file.get("FilePath"):
                tasks.append({"category": "attachment", "module": doc["module"], "id": doc["id"],
                              "url": file["FilePath"], "name": file.get("FileName", "")})
    for module, identity in [('sales','SaleId'),('sales_history_details','SaleId'),('purchases','BuyId'),('receipts','ReceiveId'),('payments','PaymentId')]:
        for row in load_rows(module):
            for key in ['ComitSignUrl','ReceiveSignUrl']:
                if isinstance(row.get(key),str) and row[key].startswith(('http://','https://','//')):
                    tasks.append({'category':'document_signature','module':module,'id':row[identity],
                                  'url':row[key],'name':key})
    for task in tasks:
        if task["url"].startswith("//"):
            task["url"] = "https:" + task["url"]
        elif task["url"].startswith("/"):
            task["url"] = "https://web.qisemiyun.com" + task["url"]
    unique = {}
    for task in tasks:
        unique.setdefault(task["url"], task)
    return tasks, list(unique.values())


def fetch_file(task):
    key = hashlib.sha256(task["url"].encode()).hexdigest()
    receipt = MEDIA / "receipts" / (key + ".json")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    if receipt.exists():
        old = json.loads(receipt.read_text(encoding="utf-8"))
        if old.get("state") == "complete" and Path(old["file"]).exists():
            return old
    last_error = None
    for attempt in range(2):
        url = task["url"]
        try:
            for redirect in range(5):
                parts = urllib.parse.urlsplit(url)
                if parts.scheme not in ("http", "https") or not parts.hostname:
                    raise ValueError("Not an HTTP file URL")
                conn = http_connection(parts.hostname, parts.port, secure=parts.scheme=="https", timeout=25, source_ip=SOURCE_IP)
                path = urllib.parse.quote(parts.path, safe="/%:@")
                if parts.query:
                    path += "?" + urllib.parse.quote(parts.query, safe="=&%:+,;@/?")
                try:
                    conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://web.qisemiyun.com/"})
                    response = conn.getresponse()
                    location = response.getheader("Location")
                    if response.status in (301, 302, 303, 307, 308) and location:
                        response.read()
                        url = urllib.parse.urljoin(url, location)
                        continue
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}")
                    extension = Path(urllib.parse.unquote(parts.path)).suffix.lower()
                    if not extension or len(extension) > 8:
                        extension = mimetypes.guess_extension((response.getheader("Content-Type") or "").split(";")[0]) or ".bin"
                    dest = MEDIA / "files" / (key + extension)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    temp = dest.with_suffix(dest.suffix + ".part")
                    digest, size = hashlib.sha256(), 0
                    with temp.open("wb") as stream:
                        while True:
                            block = response.read(1024 * 128)
                            if not block:
                                break
                            stream.write(block)
                            digest.update(block)
                            size += len(block)
                    temp.replace(dest)
                    result = {"key": key, "url": task["url"], "state": "complete", "file": str(dest),
                              "bytes": size, "sha256": digest.hexdigest(), "category": task["category"]}
                    receipt.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                    time.sleep(.1)
                    return result
                finally:
                    conn.close()
            raise RuntimeError("Too many redirects")
        except Exception as error:
            last_error = str(error)
            time.sleep(.5)
    result = {"key": key, "url": task["url"], "state": "error", "error": last_error, "category": task["category"]}
    receipt.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def main():
    MEDIA.mkdir(parents=True, exist_ok=True)
    documents = document_attachments()
    references, unique = file_tasks(documents)
    (MEDIA / "references.json").write_text(json.dumps(references, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stage": "files_start", "references": len(references), "unique_files": len(unique)}, ensure_ascii=False), flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for index, result in enumerate(pool.map(fetch_file, unique), start=1):
            results.append(result)
            if index % 100 == 0:
                print(json.dumps({"stage": "files", "processed": index, "total": len(unique),
                                  "completed": sum(x["state"] == "complete" for x in results),
                                  "bytes": sum(x.get("bytes", 0) for x in results)}), flush=True)
    manifest = {"documents": len(documents), "document_errors": [x for x in documents if x.get("error")],
                "references": len(references), "files": len(results),
                "completed": sum(x["state"] == "complete" for x in results),
                "failed": sum(x["state"] != "complete" for x in results),
                "bytes": sum(x.get("bytes", 0) for x in results), "results": results}
    (MEDIA / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "results"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
