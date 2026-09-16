# bek-v15-clean/apps/app/components/agent-builder/agent-code-workspace.tsx

- AgentCodeArtifact · type · L18-L28 — type AgentCodeArtifact = { id: string; versionId: string | null; path: string; language: string; content: string; previousContent: string | null; revision: number; status: "WRITING" | "READY"; createdAt: string; };
- AgentCodeWorkspace · function · L30-L53 — function AgentCodeWorkspace({ artifacts, working, versionId = null, }: { artifacts: AgentCodeArtifact[]; working: boolean; versionId?: string | null; })
- AgentCodeWorkspaceSurface · function · L55-L190 — function AgentCodeWorkspaceSurface({ latest, paths, working, }: { latest: Map<string, AgentCodeArtifact>; paths: string[]; working: boolean; })
