# bek-v15-clean/packages/auth/src/slack-scopes.ts

- SlackScopeGroup · type · L1-L1 — type SlackScopeGroup = "people" | "read" | "send" | "change";
- SlackScope · type · L3-L8 — type SlackScope = { scope: string; group?: SlackScopeGroup; grant: string; sensitive: boolean; };
- SlackScopeSummary · type · L154-L160 — type SlackScopeSummary = { id: SlackScopeGroup; label: string; summary: string; total: number; broad: number; };
- summariseSlackScopes · function · L162-L175 — function summariseSlackScopes( granted: readonly string[], ): SlackScopeSummary[]
- slackScopeDrift · function · L177-L188 — function slackScopeDrift(granted: readonly string[]): { extra: SlackScope[]; missing: SlackScope[]; }
- describeSlackScopes · function · L190-L200 — function describeSlackScopes(granted: readonly string[]): SlackScope[]
