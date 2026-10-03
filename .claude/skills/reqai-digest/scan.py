#!/usr/bin/env python3
"""reqai 归档增量扫描器（reqai-digest skill 的确定性部分）。

归档结构（由 reqai 服务器每日 5 次推送到本仓库）：
    reqai_archives/YYYY-MM-DD/manifest.json
    reqai_archives/YYYY-MM-DD/conversations/session-N.{md,json}
    reqai_archives/YYYY-MM-DD/files/<id>_<原名>

同一会话在每个有活动的日期下都会存一份「截至当天结束」的完整快照，
所以按会话 id 取最新日期的快照，再按消息内容哈希与 state.json 比对得出增量。

用法（在 snowmeet_ai_doc 的上一级目录或任意目录执行均可）：
    scan.py                 列出有新增/变化内容的会话（不改任何文件）
    scan.py --check         一行摘要，给 start-work 用
    scan.py --show 5 7      打印这些会话的新增/变化消息全文 + 新附件提取文本
    scan.py --show 5 --all  打印会话全部有效消息（重新分析时用）
    scan.py --mark 5 7      分析写盘后记录进度（--mark all = 当前所有待分析会话）
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

DOC_ROOT = Path(__file__).resolve().parents[3]          # snowmeet_ai_doc/
ARCHIVE_DIR = DOC_ROOT / "reqai_archives"
STATE_FILE = DOC_ROOT / "reqai_digest" / "state.json"
CST = timezone(timedelta(hours=8))


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"format_version": 1, "sessions": {}}


def msg_hash(m):
    raw = "|".join([m.get("role") or "", m.get("status") or "", m.get("content") or "",
                    json.dumps(m.get("attachment_ids"), ensure_ascii=False)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_sessions():
    """按会话 id 汇总：最新快照 + 出现过的日期 + 当日是否已封存。"""
    sessions = {}
    if not ARCHIVE_DIR.exists():
        return sessions
    for day in sorted(p for p in ARCHIVE_DIR.iterdir() if p.is_dir()):
        manifest = {}
        mf = day / "manifest.json"
        if mf.exists():
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        for jf in sorted((day / "conversations").glob("session-*.json")):
            data = json.loads(jf.read_text(encoding="utf-8"))
            sid = str(data["session"]["id"])
            entry = sessions.setdefault(sid, {"dates": []})
            entry["dates"].append(day.name)
            entry.update(data=data, date=day.name, md=jf.with_suffix(".md"),
                         complete=bool(manifest.get("complete")))
    return sessions


def analyze(sid, entry, state):
    """返回 (新增/变化消息, 新附件, 噪声说明)。"""
    data = entry["data"]
    prev = state["sessions"].get(sid, {})
    prev_msgs = prev.get("messages", {})
    prev_atts = set(prev.get("attachments", []))
    msgs = sorted(data.get("messages", []), key=lambda m: m["id"])

    noise = {}
    replied_ok = {}
    for m in msgs:
        if m["role"] == "assistant":
            ok = m.get("status") == "done" and (m.get("content") or "").strip()
            if not ok:
                noise[m["id"]] = f"无效回答（status={m.get('status')}）"
            if m.get("parent_id") is not None:
                replied_ok[m["parent_id"]] = replied_ok.get(m["parent_id"], False) or bool(ok)
    # 用户消息是需求来源，只把「回答失败、后面又原样重发」的那几条当噪声
    user_msgs = [m for m in msgs if m["role"] == "user"]
    for i, m in enumerate(user_msgs):
        text = (m.get("content") or "").strip()
        if not replied_ok.get(m["id"]) and any((n.get("content") or "").strip() == text for n in user_msgs[i + 1:]):
            noise[m["id"]] = "失败后已原样重发"

    changed = [m for m in msgs if prev_msgs.get(str(m["id"])) != msg_hash(m)]
    new_atts = [a for a in data.get("attachments", []) if a["id"] not in prev_atts]
    return changed, new_atts, noise


def pending(sessions, state):
    out = []
    for sid, entry in sorted(sessions.items(), key=lambda kv: int(kv[0])):
        changed, new_atts, noise = analyze(sid, entry, state)
        if changed or new_atts:
            out.append((sid, entry, changed, new_atts, noise))
    return out


def fmt_head(sid, entry):
    d = entry["data"]
    s, p, o = d["session"], d.get("project") or {}, d.get("owner") or {}
    lines = [f"■ 会话 #{sid}「{s.get('title')}」 所属用户：{o.get('display_name')}  模式：{s.get('mode')}",
             f"  最新快照：{entry['date']}（{'已封存' if entry['complete'] else '当日仍会更新'}）  出现日期：{', '.join(entry['dates'])}",
             f"  文件：{entry['md'].relative_to(DOC_ROOT).as_posix()}"]
    if p:
        lines.append(f"  reqai 项目：{p.get('name')}（#{p.get('id')}）  项目说明：{(p.get('instructions') or '').strip()}")
    return lines


def cmd_list(items):
    if not items:
        print("reqai 归档：没有未分析的新内容。")
        return
    for sid, entry, changed, new_atts, noise in items:
        print("\n".join(fmt_head(sid, entry)))
        if not entry["data"].get("messages"):
            print("  （空会话，没有任何消息）")
        for m in changed:
            tag = f"  ⚠ {noise[m['id']]}" if m["id"] in noise else ""
            att = f" 附件={m['attachment_ids']}" if m.get("attachment_ids") else ""
            print(f"  + msg {m['id']:>4} {m['role']:<9} {m['created_at']} {len(m.get('content') or ''):>6} 字{att}{tag}")
        for a in new_atts:
            print(f"  + 附件 {a['id']} {a['original_name']} {a.get('mime_type')} {a.get('bytes')} B "
                  f"提取文本 {len(a.get('extracted_text') or '')} 字 → {a.get('archive_path')}")
        print()
    print(f"共 {len(items)} 个会话待分析：{' '.join('#' + i[0] for i in items)}")


def cmd_show(items_by_id, sessions, ids, show_all):
    for sid in ids:
        if sid not in sessions:
            print(f"会话 #{sid} 不在归档中", file=sys.stderr)
            continue
        entry = sessions[sid]
        if sid in items_by_id and not show_all:
            _, _, changed, new_atts, noise = items_by_id[sid]
        else:
            changed, new_atts, noise = analyze(sid, entry, {"sessions": {}})
            changed = sorted(entry["data"].get("messages", []), key=lambda m: m["id"]) if show_all else []
        print("=" * 72)
        print("\n".join(fmt_head(sid, entry)))
        for m in changed:
            if m["id"] in noise:
                print(f"\n--- msg {m['id']} {m['role']} {m['created_at']} [{noise[m['id']]}，跳过正文]")
                continue
            att = f" 附件={m['attachment_ids']}" if m.get("attachment_ids") else ""
            print(f"\n--- msg {m['id']} {m['role']} {m['created_at']}{att}\n{(m.get('content') or '').strip()}")
        for a in new_atts:
            path = (entry["md"].parent.parent / a["archive_path"]).relative_to(DOC_ROOT).as_posix()
            print(f"\n--- 附件 {a['id']} {a['original_name']}（{a.get('mime_type')}）原件：{path}")
            text = (a.get("extracted_text") or "").strip()
            print(text if text else "（reqai 未提取文本；图片可用 Read 直接查看原件）")
        print()


def cmd_mark(items, sessions, state, ids):
    targets = [i[0] for i in items] if ids == ["all"] else ids
    now = datetime.now(CST).isoformat(timespec="seconds")
    for sid in targets:
        if sid not in sessions:
            print(f"会话 #{sid} 不在归档中，跳过", file=sys.stderr)
            continue
        d = sessions[sid]["data"]
        state["sessions"][sid] = {
            "title": d["session"].get("title"),
            "owner": (d.get("owner") or {}).get("display_name"),
            "project": (d.get("project") or {}).get("name"),
            "snapshot_date": sessions[sid]["date"],
            "messages": {str(m["id"]): msg_hash(m) for m in d.get("messages", [])},
            "attachments": sorted(a["id"] for a in d.get("attachments", [])),
            "marked_at": now,
        }
    state["last_run"] = now
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已记录进度：{' '.join('#' + s for s in targets if s in sessions)} → {STATE_FILE.relative_to(DOC_ROOT).as_posix()}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="reqai 归档增量扫描")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true")
    g.add_argument("--show", nargs="+", metavar="SESSION_ID")
    g.add_argument("--mark", nargs="+", metavar="SESSION_ID")
    ap.add_argument("--all", action="store_true", help="与 --show 合用：打印会话全部消息")
    args = ap.parse_args()

    state = load_state()
    sessions = load_sessions()
    items = pending(sessions, state)

    if args.check:
        if items:
            print(f"reqai 归档：{len(items)} 个会话有未分析内容（{' '.join('#' + i[0] for i in items)}），"
                  f"运行 /reqai-digest 更新需求摘要。")
        else:
            print(f"reqai 归档：无未分析内容（上次分析 {state.get('last_run', '从未')}）。")
    elif args.show:
        cmd_show({i[0]: i for i in items}, sessions, args.show, args.all)
    elif args.mark:
        cmd_mark(items, sessions, state, args.mark)
    else:
        cmd_list(items)


if __name__ == "__main__":
    main()
