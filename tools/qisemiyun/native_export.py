"""Download Qisemi's own Excel exports, including document line items."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
from pathlib import Path
from platform_support import http_connection

from client import Client, ROOT, SOURCE_IP

import xlrd

OUT = ROOT / "data"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def download(url, name):
    for _ in range(5):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("https", "http") or not parts.hostname:
            raise ValueError("Invalid export file URL")
        connection = http_connection(parts.hostname, port=parts.port, secure=parts.scheme=="https", timeout=45, source_ip=SOURCE_IP)
        path = urllib.parse.quote(parts.path, safe="/%:@")
        if parts.query:
            path += "?" + urllib.parse.quote(parts.query, safe="=&%:+,;@/?")
        try:
            connection.request("GET", path, headers={"User-Agent": "Mozilla/5.0"})
            response = connection.getresponse()
            body = response.read()
            location = response.getheader("Location")
            if response.status in (301, 302, 303, 307, 308) and location:
                url = urllib.parse.urljoin(url, location)
                continue
            if response.status != 200:
                raise RuntimeError(f"Export download HTTP {response.status}")
        finally:
            connection.close()
        extension = ".xlsx" if body.startswith(b"PK") else ".xls" if body.startswith(bytes.fromhex("D0CF11E0")) else None
        if extension is None:
            raise RuntimeError("Export download is not an Excel workbook")
        folder = OUT / "native"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / (name + extension)
        dest.write_bytes(body)
        return dest
    raise RuntimeError("Too many export download redirects")


def inspect_excel(path, job):
    if path.suffix == ".xls":
        book = xlrd.open_workbook(path)
        worksheets = [(s.name, [s.row_values(i) for i in range(s.nrows)]) for s in book.sheets()]
    else:
        import openpyxl
        # Vendor XLSX files report A1 as the used range even when they contain
        # thousands of rows. Normal loading reads the actual sheet cells.
        book = openpyxl.load_workbook(path, read_only=False, data_only=True)
        worksheets = [(s.title, list(s.values)) for s in book.worksheets]
    info = []
    for index, (name, rows) in enumerate(worksheets):
        if not rows:
            info.append({"name": name, "rows": 0})
            continue
        common_headers = {"业务日期", "单据编号", "商品编号", "商品名称", "客户名称", "供应商名称", "仓库", "备注", "数量", "名称", "名称*", "编号", "基本单位*", "分类", "期初数量", "期初单价"}
        header_index = max(range(min(8, len(rows))), key=lambda i: sum(str(v) in common_headers for v in rows[i]))
        headers, used = [], {}
        for col, value in enumerate(rows[header_index]):
            label = str(value or "").strip() or f"column_{col + 1}"
            used[label] = used.get(label, 0) + 1
            headers.append(label if used[label] == 1 else f"{label}_{used[label]}")
        target = OUT / "native_rows" / f"{job['name']}.{index + 1}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        document_numbers = set()
        with target.open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows[header_index + 1:]:
                if not any(value not in (None, "") for value in row):
                    continue
                record = dict(zip(headers, row))
                if record.get("单据编号"):
                    document_numbers.add(str(record["单据编号"]))
                stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                count += 1
        item = {"name": name, "header_row": header_index + 1, "rows": count,
                "columns": len(headers), "headers": headers, "jsonl": str(target),
                "unique_document_numbers": len(document_numbers)}
        if job.get("source_module") and job.get("document_field") and document_numbers:
            source_file = OUT / (job["source_module"] + ".jsonl")
            if source_file.exists():
                source_numbers = {str(json.loads(line).get(job["document_field"]))
                                  for line in source_file.read_text(encoding="utf-8").splitlines()}
                item["missing_documents_vs_api"] = len(source_numbers - document_numbers)
                item["extra_documents_vs_api"] = len(document_numbers - source_numbers)
        info.append(item)
    return info


def export_job(client, job):
    payload = {"Page": 1, "Rp": 10000000, "SearchType": 1, "SearchKey": "",
               "LoginClientType": 1, "AppId": 1, "VersionCode": 54,
               **job.get("payload", {})}
    status = {"name": job["name"], "label": job["label"], "state": "running", "details": True}
    status_path = OUT / "native_status" / (job["name"] + ".json")
    save(status_path, status)
    existing = list((OUT / "native").glob(job["name"] + ".xls*")) if (OUT / "native").exists() else []
    if existing and '--refresh' not in sys.argv:
        file = existing[0]
    else:
        if job.get("export_type") is not None:
            payload["ExportType"] = job["export_type"]
        if job.get("count_path"):
            result = client.post(job["count_path"], payload)
            if not result.get("IsSuccess"):
                raise RuntimeError(result.get("Message") or "Export count failed")
            status["api_export_count"] = (result.get("Data") or {}).get("Count")
            if status["api_export_count"] == 0:
                status["state"] = "empty"
                save(status_path, status)
                print(json.dumps(status, ensure_ascii=False), flush=True)
                return
        payload.update(IsUseYongYouTemplate="0", IsUseCommonTemplate="0", IsDraft=0)
        if job.get("export_type"):
            payload["IsExportDetail"] = "1"
        else:
            payload["Isexportdetailflag"] = "1"
        result = client.post(job["export_path"], payload)
        if not result.get("IsSuccess"):
            raise RuntimeError(result.get("Message") or "Native export failed")
        if job.get("status_path"):
            ready = False
            for attempt in range(120):
                time.sleep(2)
                result = client.post(job["status_path"], {"ExportType": job.get("export_type", ""), "LoginClientType": 1})
                data = result.get("Data") or {}
                if not result.get("IsSuccess"):
                    raise RuntimeError(result.get("Message") or "Export status failed")
                if str(data.get("State")) == "2":
                    url = data["FilePath"]
                    ready = True
                    break
                if attempt % 10 == 0:
                    print(json.dumps({"name": job["name"], "state": "exporting", "percent": data.get("Process")}, ensure_ascii=False), flush=True)
            if not ready:
                raise TimeoutError("Native export did not finish within the polling window")
        else:
            url = result.get("Data")
            if not isinstance(url, str):
                raise RuntimeError("Native export did not return a download URL")
        file = download(url, job["name"])
    sheets = inspect_excel(file, job)
    status.update(state="complete", file=str(file), bytes=file.stat().st_size,
                  sha256=hashlib.sha256(file.read_bytes()).hexdigest(), sheets=sheets)
    save(status_path, status)
    print(json.dumps({k: v for k, v in status.items() if k != "sheets"} | {
        "sheets": [{k: v for k, v in s.items() if k != "headers"} for s in sheets]}, ensure_ascii=False), flush=True)


def main():
    jobs = json.loads((ROOT / "native-jobs.json").read_text(encoding="utf-8"))
    only = set(x for x in sys.argv[1:] if x != '--refresh')
    client = Client.load()
    for job in jobs:
        if only and job["name"] not in only:
            continue
        try:
            export_job(client, job)
        except Exception as error:
            status = {"name": job["name"], "state": "error", "error": str(error)}
            save(OUT / "native_status" / (job["name"] + ".json"), status)
            print(json.dumps(status, ensure_ascii=False), flush=True)
        time.sleep(.8)


if __name__ == "__main__":
    main()
