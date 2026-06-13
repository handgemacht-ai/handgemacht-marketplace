# Next.js — `/__annotation_context` Route Handler

Generate an App Router route handler at `app/__annotation_context/route.ts`.

## Code

Write this file to `app/__annotation_context/route.ts` (or `src/app/__annotation_context/route.ts` if the project uses `src/`):

```typescript
import { execSync } from "child_process";
import { NextResponse } from "next/server";

function git(cmd: string): string {
  try {
    return execSync(`git ${cmd}`, { encoding: "utf-8" }).trim();
  } catch {
    return "";
  }
}

function detectWorktree(): string {
  const gitCommon = git("rev-parse --git-common-dir");
  const gitDir = git("rev-parse --git-dir");
  if (gitCommon && gitDir && gitCommon !== gitDir) {
    return process.cwd().split("/").pop() || "";
  }
  return "";
}

export async function GET() {
  return NextResponse.json({
    worktree: detectWorktree(),
    branch: git("rev-parse --abbrev-ref HEAD"),
    commit: git("rev-parse --short HEAD"),
    project: git("remote get-url origin").replace(/.*\//, "").replace(/\.git$/, ""),
    port: process.env.PORT || "3000",
  });
}
```

## Notes

- Uses App Router route handlers (Next.js 13+)
- The route is only useful in development — add `app/__annotation_context` to `.gitignore` if the team prefers, or leave it (it's harmless in production since the extension only calls it on localhost)
- If the project uses Pages Router instead, create `pages/api/__annotation_context.ts` with a standard API route handler instead
