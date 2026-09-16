# bek-v15-clean/apps/app/lib/agent-builder-state.ts

- BuilderArtifactState · type · L1-L7 — type BuilderArtifactState = { id: string; versionId: string | null; path: string; revision: number; status: "WRITING" | "READY"; };
- BuilderVersionState · type · L9-L12 — type BuilderVersionState = { id: string; status: string; };
- BuilderAgentState · type · L14-L17 — type BuilderAgentState = { status: string; currentVersion: { id: string } | null; };
- BuilderConversationState · type · L19-L25 — type BuilderConversationState = { sessionId: string | null; continuationToken: string | null; submissions: Array<{ status: string }>; createdVersions: BuilderVersionState[]; agent: BuilderAgentState | null; };
- completedBuilderSteps · function · L27-L42 — function completedBuilderSteps( artifacts: ReadonlyArray<{ path: string; createdAt: string }>, startedAt: string | null, sessionId: string | null, ): number
- builderConversationIsWorking · function · L44-L52 — function builderConversationIsWorking( conversation: BuilderConversationState, ): boolean
- builderSessionStreamKey · function · L54-L59 — function builderSessionStreamKey( sessionId: string | null, submissionId: string | null, ): string | null
- agentBuilderCallIsActive · function · L61-L104 — function agentBuilderCallIsActive( events: readonly { type: string; data?: unknown }[], ): boolean
- reviewVersionId · function · L106-L113 — function reviewVersionId( conversation: BuilderConversationState, ): string | null
- displayedArtifactVersionId · function · L115-L126 — function displayedArtifactVersionId( conversation: BuilderConversationState, working: boolean, ): string | null
- latestBuilderArtifacts · function · L128-L143 — function latestBuilderArtifacts<T extends BuilderArtifactState>( artifacts: readonly T[], versionId: string | null, ): Map<string, T>
- latestCompletedArtifactVersionId · function · L145-L153 — function latestCompletedArtifactVersionId( artifacts: readonly BuilderArtifactState[], ): string | null
- recordOf · function · L155-L159 — function recordOf(value: unknown): Record<string, unknown>
- arrayOf · function · L161-L163 — function arrayOf(value: unknown): unknown[]
