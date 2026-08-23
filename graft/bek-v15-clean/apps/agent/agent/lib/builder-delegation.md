# bek-v15-clean/apps/agent/agent/lib/builder-delegation.ts

- BuilderDelegationAction · type · L3-L7 — type BuilderDelegationAction = { callId: string; kind: string; subagentName?: string; };
- BuilderDelegationState · type · L9-L12 — type BuilderDelegationState = { turnId: string | null; callIds: string[]; };
- recordBuilderDelegation · function · L19-L45 — function recordBuilderDelegation( state: BuilderDelegationState, turnId: string, actions: readonly BuilderDelegationAction[], ): BuilderDelegationState
