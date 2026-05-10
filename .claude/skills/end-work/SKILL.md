---
name: end-work
description: Capture work session summary and project state changes before ending a session on Snowmeet AI. Use this at the end of your work day or when wrapping up a major task — triggers on "end work", "done for today", "wrapping up", "save progress", "update context", "that's all for now", or any indication that a substantial work session is complete. This ensures the project documentation stays current and future sessions have accurate context.
---

# End Work — Capture Session Summary and State

Closing a work session on an evolving project requires documenting what changed. This skill helps you capture session progress and update the project context so the next session picks up with accurate information.

## Process

1. **Summarize** what was accomplished:
   - What files were created/modified?
   - What new functionality is working?
   - What blockers or learnings emerged?
   - What's ready for the next session?

2. **Identify** what needs updating in CLAUDE.md:
   - If you completed a step in the current iteration, note which tasks moved from 🚧 to ✅
   - If you discovered new gotchas, add them to "Known issues"
   - If the "Next steps" list changed, highlight what's new
   - If you added new key files, they should be listed
   - Add a new dated entry to the dev log with today's work

3. **Prepare** the changes:
   - Draft the exact updates to CLAUDE.md (formatted as markdown)
   - Show the user what will be added
   - Ask for confirmation before updating

4. **Finalize**:
   - If approved, update CLAUDE.md with the new entries
   - Create a brief handoff note summarizing what's ready vs. what's blocked
   - Confirm all changes are saved

## Why this matters

CLAUDE.md is the single source of truth for project state. If you update it conscientiously at session end, the next session (yours or someone else's) starts informed rather than confused. This is the difference between "what was I doing?" and "I can pick this up immediately."

## Output format

Present two sections:
- **What changed** — 2–3 bullet points on accomplishments and blockers
- **Suggested updates to CLAUDE.md** — The exact text to add/modify, ready to copy in

## Example trigger phrases

- "end work"
- "done for today"
- "wrapping up"
- "let's save progress"
- "update the context"
- "save my work"
