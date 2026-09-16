# bek-v15-clean/apps/app/components/agent-builder/agent-capabilities.tsx

- Resource · type · L27-L27 — type Resource = { id: string; kind: string; label: string };
- Capabilities · type · L29-L39 — type Capabilities = { readable: boolean; problem: string | null; channel: { kind: "channel" | "user"; id: string; label: string } | null; actions: Array<{ type: string; provider: string; summary: string }>; dataScope: { mode: "SELECTED" | "WORKSPACE"; summary: string; resources: Resource[]; } | null; };
- AgentCapabilities · function · L47-L332 — function AgentCapabilities({ agentId, canManage, capabilities, }: { agentId: string; canManage: boolean; capabilities: Capabilities; })
- reset · function · L69-L73 — reset = ()
- save · function · L133-L163 — save = ()
- ResourcePicker · function · L334-L394 — function ResourcePicker({ onPick }: { onPick: (resource: Resource) => void })
- Section · function · L396-L419 — function Section({ action, children, summary, title, }: { action?: React.ReactNode; children: React.ReactNode; summary: string; title: string; })
