# bek-v15-clean/apps/agent/agent/subagents/agent_builder/lib/execution-state.ts

- BuilderAction · type · L3-L7 — type BuilderAction = { callId: string; kind: string; toolName?: string; };
- BuilderExecutionState · type · L9-L17 — type BuilderExecutionState = { turnId: string | null; stepIndex: number | null; callIds: string[]; stepCallIds: string[]; saveCallIds: string[]; savePending: boolean; saved: boolean; };
- recordBuilderActions · function · L32-L98 — function recordBuilderActions( state: BuilderExecutionState, turnId: string, stepIndex: number, actions: readonly BuilderAction[], ): BuilderExecutionState
- finishBuilderDraftSave · function · L100-L105 — function finishBuilderDraftSave( state: BuilderExecutionState, saved: boolean, ): BuilderExecutionState
- markBuilderDraftSaveFinished · function · L107-L109 — function markBuilderDraftSaveFinished(saved: boolean): void
- assertBuilderDraftOpen · function · L111-L117 — function assertBuilderDraftOpen(): void
