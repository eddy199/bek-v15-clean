# bek-v15-clean/apps/app/components/agent-builder/agent-runs-drawer.tsx

- Runs · type · L14-L14 — type Runs = RouterOutputs["agents"]["history"];
- Activity · type · L15-L15 — type Activity = RouterOutputs["agents"]["activity"];
- View · type · L22-L22 — type View = (typeof VIEWS)[number]["id"];
- AgentRunsDrawer · function · L24-L98 — function AgentRunsDrawer({ activity, cancelling, onCancel, onOpenChange, onRetry, open, retryingRunId, runs, }: { activity: Activity; agentId: string; cancelling: boolean; onCancel: (runId: string) => void; onOpenChange: (open: boolean) => void; onRetry: (runId: string) => void; open: boolean; retryingRunId?: string; runs: Runs; })
