# graft — repo map

Small markdown nodes summarising this repo. `grep` any term, symbol, or
filename here, or run `graft ask "<task>"`. Each node carries prose plus exact
`file:line`; open a source file only to edit the named span.

The same graph is queryable as MCP tools (`graft_find_code`, `graft_find_all`,
`graft_trace_calls`, `graft_file_api`, `graft_repo_map`) where a host exposes them, and
as the `graft` CLI everywhere else. Edges — who calls what — live only in the
graph, not in these files: `graft callers <symbol>` is the only way to read them.

## Concepts

- [agent-ui](agent-ui.md) — agent-ui
- [ai_service](ai_service.md) — ai_service
- [app](app.md) — app
- [check](check.md) — check
- [check_models](check_models.md) — check_models
- [config](config.md) — config
- [context_loader](context_loader.md) — context_loader
- [event_bus](event_bus.md) — event_bus
- [fast_math](fast_math.md) — fast_math
- [file_gen](file_gen.md) — file_gen
- [memory](memory.md) — memory
- [plugins](plugins.md) — plugins
- [reconciliation_job](reconciliation_job.md) — reconciliation_job
- [save_project_context](save_project_context.md) — save_project_context
- [security_guard](security_guard.md) — security_guard
- [skills](skills.md) — skills

## Files

888 per-file wiring cards mirror the source tree under `graft/` (770 carry extracted symbols). They are deliberately not enumerated here —
`grep` a symbol or `find`/`ls` a filename under `graft/` to land on the card for that file.
