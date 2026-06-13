---
name: annotation-status
description: Show a quick summary of annotation counts and recent activity. Use when the user asks about annotation status, how many are open, or wants an overview of annotations.
allowed-tools: mcp__annotation__list_annotations
user-invocable: true
---

## Annotation Status

Show a summary of annotation status for the current project.

### Step 1: Fetch counts

Make two calls to `mcp__annotation__list_annotations`:

1. With `state`: `open` — to get open annotations
2. With `state`: `resolved` — to get resolved annotations

If `${ANNOTATION_BRANCH}` is set, include it as the `branch` filter on both calls to scope to the current branch. Mention this scoping to the user.

### Step 2: Present summary

Display:

```
Annotations (branch: <branch or "all">)
  Open:     <count>
  Resolved: <count>
```

If there are open annotations, list the 5 most recent with:
- Creation date
- Creator name
- Comment text (truncated to ~80 chars)
- Target URL path
- Motivation

### Step 3: Affected domains

From the open annotations, list unique target domains with their annotation counts.

If there are open annotations, suggest: "Run `/annotation:review-annotations` to review and resolve them."
