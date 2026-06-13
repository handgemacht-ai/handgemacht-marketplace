---
name: setup-hooks
description: Generate /__annotation_context middleware for your dev server framework. Detects Next.js, Vite, or Phoenix and creates the endpoint that enriches annotations with project-specific context (worktree, branch, commit, port).
allowed-tools: Read, Write, Glob, Bash, Grep
user-invocable: true
---

## Setup Annotation Context Hooks

Generate a `/__annotation_context` endpoint for the current project's dev server. This endpoint is called by the Chrome extension when capturing annotations — it enriches each annotation with project-specific context.

### Step 1: Detect framework

Check for framework config files:

```
next.config.* → Next.js (App Router)
vite.config.*  → Vite
mix.exs with :phoenix → Phoenix
```

Use Glob to find these files. If multiple match, ask the user which framework to target. If none match, ask the user what framework they're using.

### Step 2: Determine context fields

The standard fields are always included:
- `worktree` — git worktree name (from directory name if in a linked worktree)
- `branch` — current git branch
- `commit` — current git commit (short hash)
- `project` — repository name
- `port` — dev server port

Ask the user: "Beyond the standard fields (worktree, branch, commit, project, port), do you want to expose any custom context? Examples: feature flags, A/B test variants, app version, environment name."

If the user has custom fields, incorporate them into the generated middleware.

### Step 3: Generate middleware

Read the appropriate template from `${CLAUDE_SKILL_DIR}/templates/`:
- `nextjs.md` for Next.js
- `vite.md` for Vite
- `phoenix.md` for Phoenix

Follow the template instructions to generate and write the middleware file. Adapt the code based on any custom fields from Step 2.

### Step 4: Verify

Tell the user:
1. Start or restart their dev server
2. Visit `http://localhost:<port>/__annotation_context` in the browser
3. They should see JSON with the context fields

If the endpoint returns the expected JSON, the setup is complete. The Chrome extension will automatically call this endpoint when capturing annotations.
