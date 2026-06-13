# Phoenix — `/__annotation_context` Plug

Create a Plug module and add it to the endpoint.

## Code

Write this file to `lib/<app>_web/plugs/annotation_context.ex`:

```elixir
defmodule <App>Web.Plugs.AnnotationContext do
  @moduledoc false
  import Plug.Conn

  def init(opts), do: opts

  def call(%Plug.Conn{request_path: "/__annotation_context"} = conn, _opts) do
    conn
    |> put_resp_content_type("application/json")
    |> send_resp(200, Jason.encode!(context()))
    |> halt()
  end

  def call(conn, _opts), do: conn

  defp context do
    %{
      worktree: detect_worktree(),
      branch: git(~w[rev-parse --abbrev-ref HEAD]),
      commit: git(~w[rev-parse --short HEAD]),
      project:
        git(~w[remote get-url origin])
        |> String.replace(~r|.*/|, "")
        |> String.replace(~r|\.git$|, ""),
      port: System.get_env("PORT") || "4000"
    }
  end

  defp detect_worktree do
    git_common = git(~w[rev-parse --git-common-dir])
    git_dir = git(~w[rev-parse --git-dir])

    if git_common != "" and git_dir != "" and git_common != git_dir do
      File.cwd!() |> Path.basename()
    else
      ""
    end
  end

  defp git(args) when is_list(args) do
    case System.cmd("git", args, stderr_to_stdout: true) do
      {output, 0} -> String.trim(output)
      _ -> ""
    end
  end
end
```

Then add the plug to the endpoint module (`lib/<app>_web/endpoint.ex`), **before** the router:

```elixir
plug <App>Web.Plugs.AnnotationContext
plug <App>Web.Router
```

## Notes

- Replace `<App>` and `<app>` with the actual application module name and directory
- The plug pattern-matches on `request_path` and halts — zero overhead for other requests
- Only useful in dev — wrap with `if Mix.env() == :dev` in the endpoint if preferred, but harmless in production since the extension only calls localhost
- Requires `jason` (standard Phoenix dependency)
