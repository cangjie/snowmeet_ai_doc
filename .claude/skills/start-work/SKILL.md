---
name: start-work
description: Load and display project context from CLAUDE.md at the start of your work session. Use this whenever beginning work on Snowmeet AI — whether you're continuing from yesterday, switching from another task, or jumping back in after a break. Triggers on phrases like "start work", "begin", "let's start", "what should I work on", "refresh my memory", "what's the status", or any indication of starting a new work session.
---

# Start Work — Load Project Context

Beginning a work session on a complex project requires full context. This skill ensures you immediately understand the current architecture, status, and recent progress.

## Process

1. **Read** `/Users/cangjie/Projects/snowmeet/snowmeet_ai/CLAUDE.md`
2. **Present** these sections in order:
   - **Current Status** — What's done, what's in progress, what's blocked
   - **Key Files** — The important files you'll be touching
   - **Next Steps** — The immediate priority work
   - **Known Issues** — Gotchas and constraints (things that burned us before)

3. **Format** as a scannable overview — use the exact structure from CLAUDE.md, include emojis (✅🚧⏳) to show status at a glance, and callout any blockers in bold

## Why this matters

Context switching is expensive. A project with 200+ models, 39 controllers, and 110 pages is impossible to keep in your head. By loading the documented state at the session start, you avoid the "where was I?" friction and stay in flow.

## Example trigger phrases

- "start work"
- "let's begin, what's the current status?"
- "refresh my memory on the project"
- "what should I focus on today?"
- "load context"
