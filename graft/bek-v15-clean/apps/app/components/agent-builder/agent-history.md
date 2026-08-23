# bek-v15-clean/apps/app/components/agent-builder/agent-history.tsx

- Runs · type · L25-L25 — type Runs = RouterOutputs["agents"]["history"];
- Activity · type · L26-L26 — type Activity = RouterOutputs["agents"]["activity"];
- RunRow · type · L27-L34 — type RunRow = Omit<Runs[number], "events"> & { events: Array<{ id: string; type: string; data: unknown; emittedAt: string; }>; };
- ActivityRow · type · L35-L38 — type ActivityRow = Omit<Activity[number], "before" | "after"> & { before: unknown; after: unknown; };
- AgentRuns · function · L57-L225 — function AgentRuns({ runs, onCancel, cancelling, onRetry, retryingRunId, }: { runs: Runs; onCancel: (runId: string) => void; cancelling: boolean; onRetry: (runId: string) => void; retryingRunId?: string; })
- ExpandedRun · function · L227-L304 — function ExpandedRun({ run }: { run: RunRow })
- RunMeta · function · L306-L326 — function RunMeta({ label, value, last = false, }: { label: string; value: string; last?: boolean; })
- AgentActivity · function · L328-L401 — function AgentActivity({ activity }: { activity: Activity })
- recordOf · function · L403-L407 — function recordOf(value: unknown): Record<string, unknown>
- textOf · function · L409-L411 — function textOf(value: unknown, fallback: string): string
- humanStatus · function · L413-L418 — function humanStatus(value: string): string
- formatDate · function · L420-L422 — function formatDate(value: string): string
- formatTime · function · L424-L426 — function formatTime(value: string): string
- duration · function · L428-L435 — function duration(startedAt: string | null, finishedAt: string | null): string
- eventLabel · function · L437-L440 — function eventLabel(type: string, data: unknown): string
- changeDetail · function · L442-L447 — function changeDetail(before: unknown, after: unknown): string | null
- exportJson · function · L449-L458 — function exportJson(name: string, value: unknown)
