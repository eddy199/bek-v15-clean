# bek-v15-clean/apps/app/components/agent-builder/team-agent-detail.tsx

- AgentDetail · type · L50-L50 — type AgentDetail = RouterOutputs["agents"]["byId"];
- ReviewVersion · type · L51-L51 — type ReviewVersion = AgentDetail["reviewVersion"];
- Runs · type · L52-L52 — type Runs = RouterOutputs["agents"]["history"];
- Activity · type · L53-L53 — type Activity = RouterOutputs["agents"]["activity"];
- TeamAgentDetail · function · L71-L346 — function TeamAgentDetail({ agentId, initialAgent, initialRuns, initialActivity, }: { agentId: string; initialAgent: AgentDetail; initialRuns: Runs; initialActivity: Activity; })
- invalidate · function · L104-L114 — invalidate = ()
- DraftAgentActions · function · L348-L430 — function DraftAgentActions({ agentId, name, version, }: { agentId: string; name: string; version: ReviewVersion; })
- DeleteAgentAction · function · L432-L531 — function DeleteAgentAction({ agentId, name, }: { agentId: string; name: string; })
- AgentOverview · function · L533-L565 — function AgentOverview({ agent }: { agent: AgentDetail })
- _DetailRow · function · L567-L578 — function _DetailRow({ label, value }: { label: string; value: ReactNode })
- recordOf · function · L580-L584 — function recordOf(value: unknown): Record<string, unknown>
- textOf · function · L586-L588 — function textOf(value: unknown, fallback: string): string
- formatDate · function · L590-L592 — function formatDate(value: string): string
