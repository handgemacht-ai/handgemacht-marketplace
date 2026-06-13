---
name: review-annotations
description: Review and resolve open annotations for the current branch. Fetches annotations via MCP, shows screenshots and context, fixes issues in code, and resolves each annotation. Use when the user asks to review annotations, fix visual bugs, or process annotation feedback.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, mcp__annotation__list_annotations, mcp__annotation__get_annotation_image, mcp__annotation__resolve_annotation
user-invocable: true
---

## Review Annotations

Review open annotations for the current branch, fix issues, and resolve them.

### Step 1: Fetch open annotations

Call `mcp__annotation__list_annotations` with:
- `state`: `open`
- `branch`: `${ANNOTATION_BRANCH}` (from environment, if available)

If no branch is set, call without the branch filter and tell the user you're showing all open annotations.

If no annotations are returned, tell the user there are no open annotations and stop.

### Step 2: Review each annotation

For each annotation, in order of creation (oldest first):

1. **Show summary**: Display the annotation's comment text, target URL, motivation, creator, and creation time
2. **View screenshot**: Call `mcp__annotation__get_annotation_image` with the annotation ID to see the visual context
3. **Check technical context**: Look at any `describing` body entries (console errors, network failures, web vitals) and the target selectors (CSS selector, fragment coordinates)
4. **Locate source code**: Use the target URL path and CSS selector to find the relevant source files. Use Grep and Glob to locate components or templates that render the annotated element
5. **Fix the issue**: Make the code change that addresses the annotation. Keep fixes minimal and focused
6. **Resolve**: Call `mcp__annotation__resolve_annotation` with:
   - The annotation ID
   - Resolution metadata: `commit` (current HEAD after fix), `note` (brief description of what was fixed)

After each annotation, briefly summarize what was fixed before moving to the next.

### Step 3: Summary

After all annotations are processed, show a summary:
- Total annotations reviewed
- How many were fixed and resolved
- Any that were skipped (and why)

### Rules

- Fix one annotation at a time — don't batch changes across unrelated annotations
- If an annotation requires a fix you're unsure about, describe the issue and ask the user before making changes
- If an annotation is unclear or the target can't be located, skip it and explain why
- Keep fixes minimal — address exactly what the annotation describes, nothing more
