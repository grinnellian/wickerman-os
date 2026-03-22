---
name: Store memories in project directory
description: All project memories should be stored in <project_dir>/.claude/memory/ so they're version-controlled and travel with the repo
type: feedback
---

Store all project-scoped memories in the project directory at `.claude/memory/` rather than in the home directory path.

**Why:** User wants memories to persist across environments and be part of the repo, not tied to a specific home directory.

**How to apply:** Write memory files to `<project_dir>/.claude/memory/` and maintain MEMORY.md there.
