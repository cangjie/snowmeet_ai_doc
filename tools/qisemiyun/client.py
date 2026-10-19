"""Read-only Qisemi client using the physical network interface.

Login credentials are accepted on stdin only. Session state is protected with
Windows DPAPI or macOS Keychain, outside all business repositories.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from platform_support import data_home, SessionStore, http_connection

ROOT = Path(os.environ.get("QISE_OUTPUT_ROOT", data_home())).resolve()
PUBLIC_APP = Path(os.environ.get("QISE_PUBLIC_APP", data_home() / "runtime" / "public-app.js"))
SOURCE_IP = os.environ.get("QISE_SOURCE_IP")
HOST = "web.qisemiyun.com"



def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()
                if not re.search(r"token|password|pwd|secret|sessionkey|privatekey", k, re.I)}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class Client:
    def __init__(self, session=None):
        self.session = session or {}
        app = PUBLIC_APP.read_text(encoding="utf-8")
        match = re.search(r'headers\.Sign=\w+\(\)\("5"\+\w+\+"([^"]+)"\+\w+\)', app)
        if not match:
            raise RuntimeError("Could not identify the current public request-signing format")
        self.sign_key = match.group(1)

    @classmethod
    def load(cls):
        return cls(SessionStore().load())

    def post(self, path, data=None):
        timestamp = str(int(time.time() * 1000) / 1000)
        trans = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://web.qisemiyun.com",
            "Referer": "https://web.qisemiyun.com/",
            "TimeStamp": timestamp,
            "AppId": "5",
            "TransNo": trans,
            "Sign": hashlib.md5(("5" + trans + self.sign_key + timestamp).encode()).hexdigest(),
        }
        for source, target in [("Token", "Token"), ("ContactId", "uid"), ("ProductVersion", "ProductVersion")]:
            if self.session.get(source) is not None:
                headers[target] = str(self.session[source])
        payload = {"IsOpenMultiProperty": self.session.get("IsOpenMultiProperty", 0), **(data or {})}
        connection = http_connection(HOST, timeout=35, source_ip=SOURCE_IP)
        try:
            connection.request("POST", "/api/" + path.lstrip("/"),
                               json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers)
            response = connection.getresponse()
            raw = response.read()
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status} from {path}: " + raw[:200].decode("utf-8", "replace"))
            return json.loads(raw)
        finally:
            connection.close()

    def login(self, username, password):
        result = self.post("/V1/User/Login/Login", {
            "UserLoginName": username,
            "PassWord": password,
            "LoginClientType": 1,
            "NeedCheckConflict": 1,
            "WxxdAuthKey": "",
        })
        data = result.get("Data") or {}
        if result.get("IsSuccess") and isinstance(data, dict) and data.get("Token"):
            self.session = {k: data.get(k) for k in (
                "Token", "ContactId", "UserId", "ProductVersion", "BranchId", "SOBId", "IsOpenMultiProperty", "ContactName"
            )}
            SessionStore().save(self.session)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["login", "read"])
    parser.add_argument("--path")
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.action == "login":
        credentials = json.load(sys.stdin)
        client = Client()
        result = client.login(credentials["username"], credentials["password"])
        credentials.clear()
        data = result.get("Data") or {}
        summary = {k: result.get(k) for k in ("IsSuccess", "RequestState", "Message")}
        summary["session_saved"] = bool(client.session.get("Token"))
        summary["Data_keys"] = list(data) if isinstance(data, dict) else None
        if isinstance(data, dict):
            summary.update({k: data.get(k) for k in (
                "ContactName", "ProductVersion", "IsDeadLine", "DeadLineDateStr", "IsNeedCheckConflict"
            ) if k in data})
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        if not args.path or not args.out:
            parser.error("read requires --path and --out")
        # Explicitly limit this helper to observed, read-only API endpoint names.
        tail = args.path.rstrip("/").rsplit("/", 1)[-1]
        if not re.match(r"^(Query|Get|List|Search|Check)", tail, re.I):
            raise ValueError("Only read-only endpoint names are accepted")
        client = Client.load()
        payload = json.load(sys.stdin)
        result = client.post(args.path, payload)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(redact(result), ensure_ascii=False, indent=2), encoding="utf-8")
        data = result.get("Data")
        print(json.dumps({"file": str(out.resolve()), "IsSuccess": result.get("IsSuccess"),
                          "RequestState": result.get("RequestState"), "Message": result.get("Message"),
                          "top_keys": list(result), "Data_type": type(data).__name__,
                          "Data_count": len(data) if isinstance(data, (list, dict)) else None},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
