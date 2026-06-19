---
name: end-work
description: Capture work session summary and project state changes before ending a session on Snowmeet AI. Use this at the end of your work day or when wrapping up a major task — triggers on "end work", "done for today", "wrapping up", "save progress", "update context", "that's all for now", or any indication that a substantial work session is complete. This ensures the project documentation stays current and future sessions have accurate context, and archives the session transcript to `snowmeet_ai_doc/sessions/`.
---

# End Work — Capture Session Summary, State, and Transcript

Closing a work session on an evolving project requires documenting what changed. This skill helps you capture session progress, update the project context, and archive the conversation transcript so the next session picks up with accurate information.

**项目上下文文件位置**：`snowmeet_ai_doc/CLAUDE.md`（位于仓库根目录下的 `snowmeet_ai_doc/` 目录，例如 `/Users/cangjie/source/snowmeet/snowmeet_ai/snowmeet_ai_doc/CLAUDE.md`）。所有读写都必须落到这里。

**聊天记录归档位置**：`snowmeet_ai_doc/sessions/YYYY-MM-DD_{topic}.md`。当前 working dir 下一定能找到 `snowmeet_ai_doc/sessions/` 目录（首次触发时若不存在则 `mkdir -p` 创建）。

## ⚠️ 跨机一致原则（先读这条）

本 skill 要求在**任何一台电脑**上执行都得到**相同结果**。能保证这点的唯一载体是 **SKILL.md 自身**——它在 `snowmeet_ai_doc/.claude/skills/` 内，随 git 跨机同步。所以：

- **所有关键动作（改文档、git pull / commit / push）都写进下面的 Process，靠执行 SKILL.md 完成**，绝不依赖 `.claude/settings.local.json` 里的 hook（gitignored、机器本地、不跨机）或 auto-memory（本机、不跨机）。
- 历史上 git push 曾靠某台机的 Stop hook 自动完成 → 换到没配 hook 的电脑就不 push、表现不一致。**"靠本机 hook" 的做法已废弃**：push 是下面第 6 步的固定动作。
- 本会话若产生任何影响 start-work / end-work *行为* 的规则，必须固化进本 SKILL.md 或 CLAUDE.md（git 跨机），不能只存 memory。

## Process

1. **先同步**（避免 push 被拒 / 分叉）：`git -C snowmeet_ai_doc pull --ff-only`
   - 失败（网络 / 分叉 / 本地有未提交改动）不要静默：告诉用户「⚠️ 同步失败」+ 原因，仍继续整理，到第 6 步 push 前再处理分叉

2. **Summarize** what was accomplished:
   - What files were created/modified?
   - What new functionality is working?
   - What blockers or learnings emerged?
   - What's ready for the next session?

3. **Update CLAUDE.md**（直接改，**不需要**先 draft 给用户确认——见文末「不需确认」）:
   - 完成的步骤把任务从 🚧 标到 ✅
   - 新踩的坑加进「已知遗留」
   - 「下一步」列表有变就更新
   - 新增关键文件补进「关键文件」
   - 开发日志末尾加一条当天 dated entry
   - 「当前状态」日期戳前移

4. **Memory 对账（固化进 doc）**:
   - 本会话写进 memory 的内容里，凡属*项目知识*（gotcha / 架构决策 / 状态）→ 确认 CLAUDE.md 有更完整版本，没有就补（memory 不跨机，doc 才是真源）
   - 属*个人偏好 / 本机环境*（回复语言、本机编译路径等）→ 留在 memory 即可，不塞进项目仓库
   - 凡影响本 skill *行为* 的规则 → 写进本 SKILL.md

5. **Write transcript** 到 `snowmeet_ai_doc/sessions/YYYY-MM-DD_{topic}.md`（格式见下）

6. **Commit + push（固定收尾，不需确认）**:
   - `git -C snowmeet_ai_doc add -A`
   - `git -C snowmeet_ai_doc commit -m "auto: end-work 归档 + 上下文更新（{topic}）"`
   - `git -C snowmeet_ai_doc push`
   - 每次 end-work 的强制动作，**不依赖任何本机 hook**；第 1 步 pull 若失败 / 有分叉，这里先 merge 再 push
   - 业务代码仓（SnowmeetApi / snowmeet_wechat_mini 等）**不**在此自动提交，由用户按部署节奏自行处理

7. **Handoff**: 一句话交代「已就绪 vs 仍阻塞」

## Transcript archive format

Filename: `snowmeet_ai_doc/sessions/{YYYY-MM-DD}_{short-topic-slug}.md`
- 日期用 session 起始当天（跨夜也按起始日）
- topic-slug 用英文小写 + 连字符，3-5 词概括主题（如 `rent_order_diff_and_skill`、`payment_identity_plan`、`auth_middleware_rewrite`）
- 若已存在同名文件，加 `-2` / `-3` 后缀

模板：

```markdown
# {YYYY-MM-DD} {简短标题}：{一句话概述}

按时间线/主题整理。{背景一两句，说明这场会话是接续什么任务、改动落在哪个目录}。

## 1. {主题一标题}

### 1.1 {子节}

- 关键发现/操作 1
- 关键发现/操作 2
- ...

### 1.2 {子节}

- ...

## 2. {主题二标题}

...

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `path/to/file.py` | 简述 |
| ... | ... |

## 学到的小知识

1. **{要点}**：详细解释
2. ...
```

写法原则：
- 详细到能复现 + 理解前因后果，重要 SQL/字段差异/路径要保留
- 不要事无巨细贴所有 tool call，按"做了什么、为什么、结果如何"组织
- 用户提出的核心问题/决策必须保留原话或贴近原意
- 每条 bullet 30 字内为佳；长论述用 sub-bullet 或独立段落
- 涉及代码引用用 markdown 链接到相对路径

## Why this matters

CLAUDE.md 是项目状态的单一来源；sessions/ 是工作过程的详细备查。前者让下一次会话能立即接上，后者让"那天为什么这条数据找不出来 / 减免怎么定义的"这种细节问题翻一份 markdown 即可，不用爬聊天记录。

## 不需确认（用户拍板）

触发 end-work 后**直接**落盘 CLAUDE.md + 写 sessions/ + git commit + push，**永远不要**用 AskUserQuestion 征求确认。之前"draft → 确认 → 写盘"的流程已作废。

## Output format（落盘 + push 完成后的简报）

end-work 跑完后给用户一段简报（此时文件已写、已 commit+push，不是征求确认）：
- **What changed** — 2–3 句：完成了什么、遗留什么
- **已归档** — `snowmeet_ai_doc/sessions/YYYY-MM-DD_{topic}.md` + CLAUDE.md 更新点
- **已推送** — push 成功的 commit（如 `已推送 a1b2c3d`）；若 pull/push 遇阻，说明如何处理的
- **Handoff** — 下次开工的第一件事

## Example trigger phrases

- "end work"
- "done for today"
- "wrapping up"
- "let's save progress"
- "update the context"
- "save my work"
- "今天到这"
- "收尾"
