# Vite — `/__annotation_context` Server Plugin

Add a `configureServer` plugin to `vite.config.ts` that serves the annotation context endpoint.

## Code

Add this plugin to the `plugins` array in `vite.config.ts`:

```typescript
import { execSync } from "child_process";

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

function annotationContext(): import("vite").Plugin {
  return {
    name: "annotation-context",
    configureServer(server) {
      server.middlewares.use("/__annotation_context", (_req, res) => {
        res.setHeader("Content-Type", "application/json");
        res.end(
          JSON.stringify({
            worktree: detectWorktree(),
            branch: git("rev-parse --abbrev-ref HEAD"),
            commit: git("rev-parse --short HEAD"),
            project: git("remote get-url origin").replace(/.*\//, "").replace(/\.git$/, ""),
            port: String(server.config.server.port || 5173),
          })
        );
      });
    },
  };
}
```

Then add `annotationContext()` to the `plugins` array:

```typescript
export default defineConfig({
  plugins: [
    // ... existing plugins
    annotationContext(),
  ],
});
```

## Notes

- The plugin only runs in the dev server (`configureServer` is not called during build)
- Works with Vite 4+ and 5+
- If the project uses a separate server plugin file pattern, extract the plugin there instead
