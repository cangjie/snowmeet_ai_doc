---
name: start-work
description: Load and display project context from CLAUDE.md at the start of your work session. Use this whenever beginning work on Snowmeet AI — whether you're continuing from yesterday, switching from another task, or jumping back in after a break. Triggers on phrases like "start work", "begin", "let's start", "what should I work on", "refresh my memory", "what's the status", or any indication of starting a new work session.
---

# Start Work — Load Project Context

Beginning a work session on a complex project requires full context. This skill ensures you immediately understand the current architecture, status, and recent progress.

## Process

1. **Pull** 先同步最新提交，再读上下文（**这一步必须最先做**）
   - 命令：`git -C snowmeet_ai_doc pull --ff-only`（从当前仓库根定位 `snowmeet_ai_doc/`，不要用历史遗留的 Mac 绝对路径）
   - `--ff-only`：本地有未推送提交或分叉时拒绝合并，绝不自作主张产 merge commit
   - **拉取失败（网络/分叉/本地有未提交改动）时**：不要静默继续——显式告诉用户「⚠️ 同步失败，下方上下文可能过期」并附上失败原因，再继续第 2 步
   - 拉取成功且有新提交时：一句话提示已更新到的最新 commit（如 `已更新到 dbaa546`）
2. **Read** the project context from `snowmeet_ai_doc/CLAUDE.md`
   - 该文件位于本仓库根目录下的 `snowmeet_ai_doc/` 目录（例如 `D:\snowmeet\snowmeet_ai_doc\CLAUDE.md` 或 `<repo-root>/snowmeet_ai_doc/CLAUDE.md`）
   - 不要使用历史遗留的 Mac 绝对路径（如 `/Users/cangjie/...`），改从当前仓库定位
3. **Present** these sections in order:
   - **Current Status** — What's done, what's in progress, what's blocked
   - **Key Files** — The important files you'll be touching
   - **Next Steps** — The immediate priority work
   - **Known Issues** — Gotchas and constraints (things that burned us before)

4. **Format** as a scannable overview — use the exact structure from CLAUDE.md, include emojis (✅🚧⏳) to show status at a glance, and callout any blockers in bold

## 跨机一致 & memory

本 skill 与 [end-work](../end-work/SKILL.md) 一样，靠 git 跨机同步、**自包含**：所有步骤都写在 SKILL.md 里，不依赖本机 hook 或 auto-memory。

- **真源是 `snowmeet_ai_doc/CLAUDE.md`**（git 跨机）。auto-memory 只是本机辅助提醒，换电脑会是空的——别把项目知识只放 memory。
- **新电脑首次使用**：先确认 `snowmeet_ai_doc/` 已 clone 到工作目录下、且 `/start-work` `/end-work` 出现在 skill 列表里（这俩 skill 来自 `snowmeet_ai_doc/.claude/skills/`，随仓库一起来）。没出现就说明该机没扫到子目录 skill，需要在该机做一次性补救。

## Why this matters

Context switching is expensive. A project with 200+ models, 39 controllers, and 110 pages is impossible to keep in your head. By loading the documented state at the session start, you avoid the "where was I?" friction and stay in flow.

## Example trigger phrases

- "start work"
- "let's begin, what's the current status?"
- "refresh my memory on the project"
- "what should I focus on today?"
- "load context"
